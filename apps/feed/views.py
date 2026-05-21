import base64
import logging

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.utils.response import APIResponse
from apps.contents.models import Post, PostMedia, Reel, CommunityMember
from apps.interactions.models import Like

from .serializers import NFFeedPostSerializer, NFFeedReelSerializer

logger = logging.getLogger("apps.contents")


def _annotated_media_qs(user=None):
    """Annotated PostMedia queryset — like/comment counts + is_liked per user."""
    qs = PostMedia.objects.annotate(
        like_count=Count("likes", distinct=True),
        comment_count=Count("comments", distinct=True),
    ).order_by("order")
    if user:
        media_ct = ContentType.objects.get_for_model(PostMedia)
        qs = qs.annotate(
            is_liked=Exists(
                Like.objects.filter(
                    content_type=media_ct,
                    object_id=OuterRef("pk"),
                    user=user,
                )
            )
        )
    return qs


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


class PostNewsFeedView(APIView):
    """All public posts from all users, newest first."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        page_size = _parse_page_size(request)
        post_ct = ContentType.objects.get_for_model(Post)

        qs = (
            Post.objects.filter(privacy=Post.Privacy.PUBLIC)
            .filter(
                models.Q(community__isnull=True)
                | models.Q(
                    community__members__user=request.user
                )  # community posts where user is member
            )
            .distinct()
            .select_related("author")
            .prefetch_related(
                Prefetch("media", queryset=_annotated_media_qs(request.user))
            )
            .annotate(
                media_count=Count("media", distinct=True),
                like_count=Count("likes", distinct=True),
                comment_count=Count("comments", distinct=True),
                is_liked=Exists(
                    Like.objects.filter(
                        content_type=post_ct,
                        object_id=OuterRef("pk"),
                        user=request.user,
                    )
                ),
            )
            .order_by("-created_at", "-id")
        )

        cursor_str = request.query_params.get("cursor")
        if cursor_str:
            decoded = _decode_cursor(cursor_str)
            if not decoded:
                logger.warning("Bad feed cursor | user_id=%s", request.user.pk)
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

        next_cursor = (
            _encode_cursor(items[-1].created_at, items[-1].id) if has_more else None
        )

        logger.debug(
            "Post news feed | user_id=%s page_size=%s has_more=%s",
            request.user.pk,
            page_size,
            has_more,
        )
        return APIResponse.success(
            data=NFFeedPostSerializer(
                items, many=True, context={"request": request}
            ).data,
            meta={
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": page_size,
            },
        )


class ReelNewsFeedView(APIView):
    """Unified reel feed — direct reels + post videos merged."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        page_size = _parse_page_size(request)
        reel_ct = ContentType.objects.get_for_model(Reel)
        media_ct = ContentType.objects.get_for_model(PostMedia)

        cursor_str = request.query_params.get("cursor")
        cursor_filter = {}
        if cursor_str:
            decoded = _decode_cursor(cursor_str)
            if not decoded:
                logger.warning("Bad reel feed cursor | user_id=%s", request.user.pk)
                return APIResponse.error(
                    errors={"cursor": "Invalid or tampered cursor."}, status_code=400
                )
            cursor_filter["created_at_str"], cursor_filter["obj_id"] = decoded

        fetch_limit = page_size * 2

        # Direct reels
        direct_qs = (
            Reel.objects.filter(privacy=Reel.Privacy.PUBLIC)
            .select_related("author")
            .annotate(
                like_count=Count("likes", distinct=True),
                comment_count=Count("comments", distinct=True),
                is_liked=Exists(
                    Like.objects.filter(
                        content_type=reel_ct,
                        object_id=OuterRef("pk"),
                        user=request.user,
                    )
                ),
            )
            .order_by("-created_at", "-id")
        )
        if cursor_filter:
            direct_qs = direct_qs.filter(
                Q(created_at__lt=cursor_filter["created_at_str"])
                | Q(
                    created_at=cursor_filter["created_at_str"],
                    id__lt=cursor_filter["obj_id"],
                )
            )
        direct_reels = list(direct_qs[:fetch_limit])

        # Post videos
        post_video_qs = (
            PostMedia.objects.filter(
                media_type=PostMedia.MediaType.VIDEO,
                post__privacy=Post.Privacy.PUBLIC,
            )
            .filter(
                models.Q(post__community__isnull=True)
                | models.Q(post__community__members__user=request.user)
            )
            .distinct()
            .select_related("post__author")
            .annotate(
                like_count=Count("likes", distinct=True),
                comment_count=Count("comments", distinct=True),
                is_liked=Exists(
                    Like.objects.filter(
                        content_type=media_ct,
                        object_id=OuterRef("pk"),
                        user=request.user,
                    )
                ),
            )
            .order_by("-created_at", "-id")
        )
        if cursor_filter:
            post_video_qs = post_video_qs.filter(
                Q(created_at__lt=cursor_filter["created_at_str"])
                | Q(
                    created_at=cursor_filter["created_at_str"],
                    id__lt=cursor_filter["obj_id"],
                )
            )
        post_videos = list(post_video_qs[:fetch_limit])

        # Normalise into unified dict
        unified = []

        for r in direct_reels:
            unified.append(
                {
                    "id": r.id,
                    "source": "direct",
                    "author": r.author,
                    "caption": r.caption,
                    "video_url": request.build_absolute_uri(r.video.url),
                    "privacy": r.privacy,
                    "like_count": r.like_count,
                    "comment_count": r.comment_count,
                    "is_liked": r.is_liked,
                    "view_count": r.view_count,
                    "created_at": r.created_at,
                }
            )

        for pm in post_videos:
            unified.append(
                {
                    "id": pm.id,
                    "source": "post",
                    "author": pm.post.author,
                    "caption": pm.caption,
                    "video_url": request.build_absolute_uri(pm.file.url),
                    "privacy": pm.post.privacy,
                    "like_count": pm.like_count,
                    "comment_count": pm.comment_count,
                    "is_liked": pm.is_liked,
                    "view_count": pm.view_count,
                    "created_at": pm.created_at,
                }
            )

        unified.sort(key=lambda x: (x["created_at"], str(x["id"])), reverse=True)

        has_more = len(unified) > page_size
        unified = unified[:page_size]

        next_cursor = None
        if has_more and unified:
            last = unified[-1]
            next_cursor = _encode_cursor(last["created_at"], last["id"])

        logger.debug(
            "Reel news feed | user_id=%s page_size=%s has_more=%s",
            request.user.pk,
            page_size,
            has_more,
        )
        return APIResponse.success(
            data=NFFeedReelSerializer(
                unified, many=True, context={"request": request}
            ).data,
            meta={
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": page_size,
            },
        )


class CommunityPostFeedView(APIView):
    """Posts from a specific community, newest first."""

    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        if not CommunityMember.objects.filter(
            user=request.user, community_id=community_id
        ).exists():
            return APIResponse.error(
                errors={"detail": "You are not a member of this community."},
                status_code=403,
            )

        page_size = _parse_page_size(request)
        post_ct = ContentType.objects.get_for_model(Post)

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
                is_liked=Exists(
                    Like.objects.filter(
                        content_type=post_ct,
                        object_id=OuterRef("pk"),
                        user=request.user,
                    )
                ),
            )
            .order_by("-created_at", "-id")
        )

        cursor_str = request.query_params.get("cursor")
        if cursor_str:
            decoded = _decode_cursor(cursor_str)
            if not decoded:
                logger.warning(
                    "Bad community feed cursor | user_id=%s community_id=%s",
                    request.user.pk,
                    community_id,
                )
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

        next_cursor = (
            _encode_cursor(items[-1].created_at, items[-1].id) if has_more else None
        )

        logger.debug(
            "Community post feed | user_id=%s community_id=%s page_size=%s has_more=%s",
            request.user.pk,
            community_id,
            page_size,
            has_more,
        )
        return APIResponse.success(
            data=NFFeedPostSerializer(
                items, many=True, context={"request": request}
            ).data,
            meta={
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": page_size,
            },
        )
