import base64
import logging
from uuid import UUID

from django.core.cache import caches
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.utils.throttles import FeedThrottle
from apps.utils.response import APIResponse
from apps.contents.models import Post, PostMedia, Reel, CommunityMember, SavedItem
from apps.contents.views import _attach_top_reacts, _user_reaction_subquery
from .serializers import NFFeedPostSerializer, NFFeedReelSerializer

logger = logging.getLogger("apps.contents")

FEED_CACHE_TTL = 60
FEED_PAGE_CACHE_TTL = 120
SEEN_TTL = 7 * 24 * 3600


# Seen-set helpers (Redis) - tracks what each user already received in the feed

def _redis():
    return caches["default"].client.get_client()


def _seen_key(user_id, feed_type):
    return caches["default"].make_key(f"feed:seen:{feed_type}:{user_id}")


def _get_seen(user_id, feed_type):
    raw = _redis().smembers(_seen_key(user_id, feed_type))
    return {m.decode() if isinstance(m, bytes) else m for m in raw}


def _mark_seen(user_id, feed_type, keys):
    if not keys:
        return
    redis_key = _seen_key(user_id, feed_type)
    client = _redis()
    client.sadd(redis_key, *keys)
    client.expire(redis_key, SEEN_TTL)


def _clear_seen(user_id, feed_type):
    _redis().delete(_seen_key(user_id, feed_type))


def _seen_uuids(seen, prefix):
    ids = []
    for key in seen:
        if key.startswith(f"{prefix}:"):
            try:
                ids.append(UUID(key.split(":", 1)[1]))
            except ValueError:
                continue
    return ids


# Cache helpers (community feed only)

def _feed_cache_key(prefix, user_id, cursor=None, extra=None, page_size=None):
    parts = [prefix, str(user_id), cursor or "page1"]
    if page_size is not None:
        parts.append(f"ps{page_size}")
    if extra:
        parts.append(str(extra))
    return ":".join(parts)


def invalidate_user_feed(user_id):
    """
    Kept for call-site compatibility.
    Seen-based feeds track per-item state in Redis; new content is picked up
    automatically because it is not in the seen set.
    """
    return


def invalidate_community_feed(community_id):
    cache = caches["default"]
    cache.delete_many([f"feed:community:{community_id}:*"])


# Query helpers

def _annotated_media_qs(user):
    media_ct = ContentType.objects.get_for_model(PostMedia)
    return PostMedia.objects.annotate(
        like_count=Count("likes", distinct=True),
        comment_count=Count("comments", distinct=True),
        user_reaction=_user_reaction_subquery(media_ct, user),
    ).order_by("order")


def _encode_cursor(created_at, obj_id):
    raw = f"{created_at.isoformat()}__{obj_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor_str):
    try:
        raw = base64.urlsafe_b64decode(cursor_str.encode()).decode()
        created_at_str, obj_id = raw.split("__", 1)
        return created_at_str, obj_id
    except Exception:
        return None


def _parse_page_size(request, default=10):
    try:
        return min(int(request.query_params.get("page_size", default)), 50)
    except (TypeError, ValueError):
        return default


def _post_feed_qs(user, post_ct):
    return (
        Post.objects.filter(privacy=Post.Privacy.PUBLIC)
        .filter(Q(community__isnull=True) | Q(community__members__user=user))
        .distinct()
        .select_related("author", "community")
        .prefetch_related(Prefetch("media", queryset=_annotated_media_qs(user)))
        .annotate(
            media_count=Count("media", distinct=True),
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
            user_reaction=_user_reaction_subquery(post_ct, user),
            is_saved=Exists(
                SavedItem.objects.filter(
                    content_type=post_ct,
                    object_id=OuterRef("pk"),
                    user=user,
                )
            ),
        )
        .order_by("-created_at", "-id")
    )


def _next_unseen_posts(user, page_size, seen):
    """Return (items, has_more, seen_keys). Resets seen set when pool is exhausted."""
    post_ct = ContentType.objects.get_for_model(Post)
    qs = _post_feed_qs(user, post_ct)
    if seen:
        qs = qs.exclude(id__in=_seen_uuids(seen, "post"))

    items = list(qs[: page_size + 1])
    if not items and seen:
        _clear_seen(user.pk, "posts")
        items = list(_post_feed_qs(user, post_ct)[: page_size + 1])

    has_more = len(items) > page_size
    if has_more:
        items = items[:page_size]
    keys = [f"post:{p.id}" for p in items]
    return items, has_more, keys, post_ct


# Views

class PostNewsFeedView(APIView):
    """
    Public post feed, newest first.
    Each request returns the next batch of unseen posts; cycles when all are seen.
    Search bypasses seen tracking.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [FeedThrottle]

    def get(self, request):
        page_size = _parse_page_size(request)
        search = request.query_params.get("search", "").strip()
        post_ct = ContentType.objects.get_for_model(Post)

        if search:
            qs = _post_feed_qs(request.user, post_ct).filter(caption__icontains=search)
            items = list(qs[:page_size])
            _attach_top_reacts(items, post_ct)
            _attach_top_reacts(
                [m for post in items for m in post.media.all()],
                ContentType.objects.get_for_model(PostMedia),
            )
            data = NFFeedPostSerializer(
                items, many=True, context={"request": request}
            ).data
            return APIResponse.success(
                data=data,
                meta={
                    "next_cursor": None,
                    "has_more": False,
                    "page_size": page_size,
                },
            )

        seen = _get_seen(request.user.pk, "posts")
        items, has_more, keys, post_ct = _next_unseen_posts(
            request.user, page_size, seen
        )
        _mark_seen(request.user.pk, "posts", keys)

        _attach_top_reacts(items, post_ct)
        _attach_top_reacts(
            [m for post in items for m in post.media.all()],
            ContentType.objects.get_for_model(PostMedia),
        )

        next_cursor = (
            _encode_cursor(items[-1].created_at, items[-1].id)
            if has_more and items
            else None
        )
        data = NFFeedPostSerializer(items, many=True, context={"request": request}).data
        meta = {
            "next_cursor": next_cursor,
            "has_more": has_more,
            "page_size": page_size,
        }

        logger.debug(
            "Post feed | user=%s count=%s has_more=%s seen_total=%s",
            request.user.pk,
            len(items),
            has_more,
            len(seen) + len(keys),
        )
        return APIResponse.success(data=data, meta=meta)


class FeedPostDetailView(APIView):
    """Single post from the news feed — same shape as feed list items."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [FeedThrottle]

    def get(self, request, pk):
        post_ct = ContentType.objects.get_for_model(Post)
        media_ct = ContentType.objects.get_for_model(PostMedia)

        try:
            post = _post_feed_qs(request.user, post_ct).get(pk=pk)
        except Post.DoesNotExist:
            return APIResponse.error(message="Post not found.", status_code=404)

        _attach_top_reacts([post], post_ct)
        _attach_top_reacts(list(post.media.all()), media_ct)

        return APIResponse.success(
            data=NFFeedPostSerializer(post, context={"request": request}).data
        )


def _reel_to_dict(r, request):
    return {
        "id": r.id,
        "source": "direct",
        "author": r.author,
        "caption": r.caption,
        "video_url": request.build_absolute_uri(r.video.url),
        "privacy": r.privacy,
        "like_count": r.like_count,
        "comment_count": r.comment_count,
        "user_reaction": getattr(r, "user_reaction", None),
        "top_reacts": getattr(r, "top_reacts", []),
        "is_saved": r.is_saved,
        "view_count": r.view_count,
        "created_at": r.created_at,
        "_seen_key": f"reel:{r.id}",
    }


def _post_video_to_dict(pm, request):
    return {
        "id": pm.id,
        "source": "post",
        "author": pm.post.author,
        "caption": pm.caption,
        "video_url": request.build_absolute_uri(pm.file.url),
        "privacy": pm.post.privacy,
        "like_count": pm.like_count,
        "comment_count": pm.comment_count,
        "user_reaction": getattr(pm, "user_reaction", None),
        "top_reacts": getattr(pm, "top_reacts", []),
        "is_saved": pm.is_saved,
        "view_count": pm.view_count,
        "created_at": pm.created_at,
        "_seen_key": f"post_video:{pm.id}",
    }


def _fetch_reel_candidates(user, request, seen, fetch_limit):
    reel_ct = ContentType.objects.get_for_model(Reel)
    media_ct = ContentType.objects.get_for_model(PostMedia)

    direct_qs = (
        Reel.objects.filter(privacy=Reel.Privacy.PUBLIC)
        .select_related("author")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
            user_reaction=_user_reaction_subquery(reel_ct, user),
            is_saved=Exists(
                SavedItem.objects.filter(
                    content_type=reel_ct,
                    object_id=OuterRef("pk"),
                    user=user,
                )
            ),
        )
        .order_by("-created_at", "-id")
    )
    reel_seen = _seen_uuids(seen, "reel")
    if reel_seen:
        direct_qs = direct_qs.exclude(id__in=reel_seen)

    post_video_qs = (
        PostMedia.objects.filter(
            media_type=PostMedia.MediaType.VIDEO,
            post__privacy=Post.Privacy.PUBLIC,
        )
        .filter(
            Q(post__community__isnull=True)
            | Q(post__community__members__user=user)
        )
        .distinct()
        .select_related("post__author")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
            user_reaction=_user_reaction_subquery(media_ct, user),
            is_saved=Exists(
                SavedItem.objects.filter(
                    content_type=media_ct,
                    object_id=OuterRef("pk"),
                    user=user,
                )
            ),
        )
        .order_by("-created_at", "-id")
    )
    video_seen = _seen_uuids(seen, "post_video")
    if video_seen:
        post_video_qs = post_video_qs.exclude(id__in=video_seen)

    direct_reels = list(direct_qs[:fetch_limit])
    post_videos = list(post_video_qs[:fetch_limit])
    _attach_top_reacts(direct_reels, reel_ct)
    _attach_top_reacts(post_videos, media_ct)

    unified = [_reel_to_dict(r, request) for r in direct_reels] + [
        _post_video_to_dict(pm, request) for pm in post_videos
    ]
    unified.sort(key=lambda x: (x["created_at"], str(x["id"])), reverse=True)
    return unified


class ReelNewsFeedView(APIView):
    """
    Unified reel feed — direct reels + post videos, newest first.
    Each request returns the next batch of unseen items; cycles when all are seen.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [FeedThrottle]

    def get(self, request):
        page_size = _parse_page_size(request)
        user = request.user
        seen = _get_seen(user.pk, "reels")
        fetch_limit = page_size * 3

        unified = _fetch_reel_candidates(user, request, seen, fetch_limit)
        if not unified and seen:
            _clear_seen(user.pk, "reels")
            seen = set()
            unified = _fetch_reel_candidates(user, request, seen, fetch_limit)

        has_more = len(unified) > page_size
        page = unified[:page_size]
        keys = [item["_seen_key"] for item in page]
        _mark_seen(user.pk, "reels", keys)

        for item in page:
            item.pop("_seen_key", None)

        next_cursor = (
            _encode_cursor(page[-1]["created_at"], page[-1]["id"])
            if has_more and page
            else None
        )
        data = NFFeedReelSerializer(page, many=True, context={"request": request}).data
        meta = {
            "next_cursor": next_cursor,
            "has_more": has_more,
            "page_size": page_size,
        }

        logger.debug(
            "Reel feed | user=%s count=%s has_more=%s seen_total=%s",
            user.pk,
            len(page),
            has_more,
            len(seen) + len(keys),
        )
        return APIResponse.success(data=data, meta=meta)


class CommunityPostFeedView(APIView):
    """
    Posts from a specific community, newest first.
    Cached per community per user per page.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [FeedThrottle]

    def get(self, request, community_id):
        if not CommunityMember.objects.filter(
            user=request.user, community_id=community_id
        ).exists():
            return APIResponse.error(
                errors={"detail": "You are not a member of this community."},
                status_code=403,
            )

        page_size = _parse_page_size(request)
        search = request.query_params.get("search", "").strip()
        cursor_str = request.query_params.get("cursor")

        if not search:
            cache_key = _feed_cache_key(
                "feed:community",
                request.user.pk,
                cursor_str,
                extra=community_id,
                page_size=page_size,
            )
            cached = caches["default"].get(cache_key)
            if cached:
                logger.debug(
                    "Community feed cache hit | user=%s community=%s",
                    request.user.pk,
                    community_id,
                )
                return APIResponse.success(**cached)

        post_ct = ContentType.objects.get_for_model(Post)
        member_count = CommunityMember.objects.filter(community_id=community_id).count()

        qs = (
            Post.objects.filter(community_id=community_id)
            .select_related("author", "community")
            .prefetch_related(
                Prefetch("media", queryset=_annotated_media_qs(request.user))
            )
            .annotate(
                media_count=Count("media", distinct=True),
                like_count=Count("likes", distinct=True),
                comment_count=Count("comments", distinct=True),
                user_reaction=_user_reaction_subquery(post_ct, request.user),
            )
            .order_by("-created_at", "-id")
        )

        if search:
            qs = qs.filter(caption__icontains=search)

        if cursor_str:
            decoded = _decode_cursor(cursor_str)
            if not decoded:
                return APIResponse.error(
                    errors={"cursor": "Invalid or tampered cursor."}, status_code=400
                )
            created_at_str, post_id = decoded
            qs = qs.filter(
                Q(created_at__lt=created_at_str)
                | Q(created_at=created_at_str, id__lt=post_id)
            )

        items = list(qs[: page_size + 1])
        has_more = len(items) > page_size
        if has_more:
            items = items[:page_size]

        _attach_top_reacts(items, post_ct)

        next_cursor = (
            _encode_cursor(items[-1].created_at, items[-1].id) if has_more else None
        )
        data = NFFeedPostSerializer(items, many=True, context={"request": request}).data
        meta = {
            "next_cursor": next_cursor,
            "has_more": has_more,
            "page_size": page_size,
            "member_count": member_count,
        }

        if not search:
            ttl = FEED_CACHE_TTL if not cursor_str else FEED_PAGE_CACHE_TTL
            caches["default"].set(cache_key, {"data": data, "meta": meta}, ttl)

        logger.debug(
            "Community feed | user=%s community=%s has_more=%s",
            request.user.pk,
            community_id,
            has_more,
        )
        return APIResponse.success(data=data, meta=meta)
