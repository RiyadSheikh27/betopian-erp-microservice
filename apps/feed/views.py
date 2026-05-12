import base64
import logging

from django.db.models import Count, Q
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.utils.response import APIResponse
from apps.contents.models import Post, PostMedia, Reel
from .serializers import NFFeedPostSerializer, NFFeedReelSerializer

logger = logging.getLogger("apps.contents")


"""HELPER FUNCTIONS """


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


"""NEWS FEED VIEWS """


class PostNewsFeedView(APIView):
    """
    All public posts from all users, newest first.
    Response shape is identical to the own-post list so the
    client uses one model for both screens.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        page_size = _parse_page_size(request)

        qs = (
            Post.objects.filter(privacy=Post.Privacy.PUBLIC)
            .select_related("author")
            .prefetch_related("media")
            .annotate(media_count=Count("media"))
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
    """
    Unified reel feed from two sources:
      1. Direct reels  (Reel model, privacy=public)
      2. Post videos   (PostMedia, media_type=video, post privacy=public)

    Both are normalised into one dict shape, merged in Python,
    then cursor-sorted so the feed is seamless.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        page_size = _parse_page_size(request)

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

        # Fetch 2× page_size from each source so after merging
        # we always have enough to fill the page even if one source is sparse.
        fetch_limit = page_size * 2

        # For reels
        direct_qs = (
            Reel.objects.filter(privacy=Reel.Privacy.PUBLIC)
            .select_related("author")
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

        # For post videos
        post_video_qs = (
            PostMedia.objects.filter(
                media_type=PostMedia.MediaType.VIDEO,
                post__privacy=Post.Privacy.PUBLIC,
            )
            .select_related("post__author")
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

        # Normalise both sources into a unified dict shape
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
                    "view_count": pm.view_count,  # CHANGED — was hardcoded 0
                    "created_at": pm.created_at,
                }
            )

        # Sort merged list newest-first, matching DB ordering
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
