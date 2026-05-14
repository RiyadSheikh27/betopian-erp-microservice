import base64
import logging

from django.db.models import Count, F, Prefetch
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from apps.utils.response import APIResponse
from .models import Post, PostMedia, Reel
from .serializers import (
    PostSerializer,
    PostCreateSerializer,
    PostUpdateSerializer,
    ReelSerializer,
    ReelCreateSerializer,
    ReelUpdateSerializer,
)

logger = logging.getLogger("apps.contents")

""" HELPER FUNCTIONS """


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


def _apply_cursor(queryset, cursor_str):
    """Filter queryset to items older than the cursor. Returns (qs, error|None)."""

    from django.db.models import Q

    decoded = _decode_cursor(cursor_str)
    if not decoded:
        return queryset, "Invalid or tampered cursor."
    created_at_str, obj_id = decoded
    qs = queryset.filter(
        Q(created_at__lt=created_at_str) | Q(created_at=created_at_str, id__lt=obj_id)
    )
    return qs, None


def _paginate_cursor(queryset, page_size):
    """Fetch page_size+1 rows to detect has_more without a COUNT query.
    Returns (items, has_more, next_cursor | None)."""

    items = list(queryset[: page_size + 1])
    has_more = len(items) > page_size
    if has_more:
        items = items[:page_size]
    next_cursor = (
        _encode_cursor(items[-1].created_at, items[-1].id) if has_more else None
    )
    return items, has_more, next_cursor


def _post_queryset():
    return (
        Post.objects.select_related("author")
        .prefetch_related(Prefetch("media", queryset=_annotated_media_qs()))
        .annotate(
            media_count=Count("media", distinct=True),
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
        )
        .order_by("-created_at", "-id")
    )


def _reel_queryset():
    return (
        Reel.objects.select_related("author")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
        )
        .order_by("-created_at", "-id")
    )

def _parse_page_size(request, default=10):
    try:
        return min(int(request.query_params.get("page_size", default)), 50)
    except (TypeError, ValueError):
        return default
    
def _annotated_media_qs():
    return PostMedia.objects.annotate(
        like_count=Count("likes", distinct=True),
        comment_count=Count("comments", distinct=True),
    ).order_by("order")


""" POST SECTION VIEWS"""


class PostListCreateView(APIView):
    """List and Create Own Posts."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        """Own post list - cursor paginated."""
        page_size = _parse_page_size(request)
        qs = _post_queryset().filter(author=request.user)

        cursor_str = request.query_params.get("cursor")
        if cursor_str:
            qs, err = _apply_cursor(qs, cursor_str)
            if err:
                logger.warning(
                    "Bad cursor | user_id=%s cursor=%s", request.user.pk, cursor_str
                )
                return APIResponse.error(errors={"cursor": err}, status_code=400)

        items, has_more, next_cursor = _paginate_cursor(qs, page_size)
        logger.debug(
            "Own post list | user_id=%s page_size=%s has_more=%s",
            request.user.pk,
            page_size,
            has_more,
        )
        return APIResponse.success(
            data=PostSerializer(items, many=True, context={"request": request}).data,
            meta={
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": page_size,
            },
        )

    def post(self, request):
        """Upload a new post with multiple media files."""
        files = request.FILES.getlist("files")
        captions = request.data.getlist("captions")
        data = {
            "caption": request.data.get("caption", ""),
            "privacy": request.data.get("privacy", Post.Privacy.PUBLIC),
            "uploaded_files": files,
            "captions": captions,
        }
        serializer = PostCreateSerializer(data=data)
        if not serializer.is_valid():
            logger.warning(
                "Post create failed | user_id=%s errors=%s",
                request.user.pk,
                serializer.errors,
            )
            return APIResponse.error(
                errors=serializer.errors, message="Post creation failed."
            )

        post = serializer.save(author=request.user)
        logger.info(
            "Post created | user_id=%s post_id=%s media=%s",
            request.user.pk,
            post.pk,
            len(files),
        )

        post = _post_queryset().get(pk=post.pk)
        return APIResponse.success(
            data=PostSerializer(post, context={"request": request}).data,
            message="Post created successfully.",
            status_code=201,
        )


class PostDetailView(APIView):
    """Retrieve, Update and Delete Own Post."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def _get_own_post(self, pk, user):
        try:
            return _post_queryset().get(pk=pk, author=user)
        except Post.DoesNotExist:
            logger.warning("Post not found | user_id=%s post_id=%s", user.pk, pk)
            return None

    def get(self, request, pk):
        post = self._get_own_post(pk, request.user)
        if not post:
            return APIResponse.error(message="Post not found.", status_code=404)
        return APIResponse.success(
            data=PostSerializer(post, context={"request": request}).data
        )

    def patch(self, request, pk):
        """Update a post. All fields optional."""
        post = self._get_own_post(pk, request.user)
        if not post:
            return APIResponse.error(message="Post not found.", status_code=404)

        data = {
            "caption": request.data.get("caption", post.caption),
            "privacy": request.data.get("privacy", post.privacy),
            "add_files": request.FILES.getlist("add_files"),
            "add_captions": request.data.getlist("add_captions"),
            "remove_media_ids": request.data.getlist("remove_media_ids"),
            "edit_media_id": request.data.getlist("edit_media_id"),
            "edit_media_caption": request.data.getlist("edit_media_caption"),
        }
        serializer = PostUpdateSerializer(post, data=data, partial=True)
        if not serializer.is_valid():
            logger.warning(
                "Post update failed | user_id=%s post_id=%s errors=%s",
                request.user.pk,
                pk,
                serializer.errors,
            )
            return APIResponse.error(errors=serializer.errors)

        updated = serializer.save()
        logger.info(
            "Post updated | user_id=%s post_id=%s added=%s removed=%s",
            request.user.pk,
            pk,
            len(data["add_files"]),
            len(data["remove_media_ids"]),
        )
        updated = _post_queryset().get(pk=updated.pk)
        return APIResponse.success(
            data=PostSerializer(updated, context={"request": request}).data,
            message="Post updated successfully.",
        )

    def delete(self, request, pk):
        post = self._get_own_post(pk, request.user)
        if not post:
            return APIResponse.error(message="Post not found.", status_code=404)
        post.delete()
        logger.info("Post deleted | user_id=%s post_id=%s", request.user.pk, pk)
        return APIResponse.success(message="Post deleted successfully.")


""" REELS SECTION VIEWS """


class ReelListCreateView(APIView):
    """List and Create Own Reels."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        """Own reels list - cursor paginated."""
        page_size = _parse_page_size(request)
        qs = _reel_queryset().filter(author=request.user)

        cursor_str = request.query_params.get("cursor")
        if cursor_str:
            qs, err = _apply_cursor(qs, cursor_str)
            if err:
                logger.warning(
                    "Bad cursor | user_id=%s cursor=%s", request.user.pk, cursor_str
                )
                return APIResponse.error(errors={"cursor": err}, status_code=400)

        items, has_more, next_cursor = _paginate_cursor(qs, page_size)
        logger.debug(
            "Own reel list | user_id=%s has_more=%s", request.user.pk, has_more
        )
        return APIResponse.success(
            data=ReelSerializer(items, many=True, context={"request": request}).data,
            meta={
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": page_size,
            },
        )

    def post(self, request):
        """Upload a direct reel (single video + caption)."""

        serializer = ReelCreateSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                "Reel create failed | user_id=%s errors=%s",
                request.user.pk,
                serializer.errors,
            )
            return APIResponse.error(
                errors=serializer.errors, message="Reel creation failed."
            )

        reel = serializer.save(author=request.user)
        logger.info("Reel created | user_id=%s reel_id=%s", request.user.pk, reel.pk)
        return APIResponse.success(
            data=ReelSerializer(reel, context={"request": request}).data,
            message="Reel created successfully.",
            status_code=201,
        )


class ReelDetailView(APIView):
    """Retrieve, Update and Delete Own Reel."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def _get_own_reel(self, pk, user):
        try:
            return _reel_queryset().get(pk=pk, author=user)
        except Reel.DoesNotExist:
            logger.warning("Reel not found | user_id=%s reel_id=%s", user.pk, pk)
            return None

    def get(self, request, pk):
        """Retrieve own reel details."""
        reel = self._get_own_reel(pk, request.user)
        if not reel:
            return APIResponse.error(message="Reel not found.", status_code=404)
        return APIResponse.success(
            data=ReelSerializer(reel, context={"request": request}).data
        )

    def patch(self, request, pk):
        """Update reel caption or privacy. Video cannot be changed."""
        reel = self._get_own_reel(pk, request.user)
        if not reel:
            return APIResponse.error(message="Reel not found.", status_code=404)

        serializer = ReelUpdateSerializer(reel, data=request.data, partial=True)
        if not serializer.is_valid():
            logger.warning(
                "Reel update failed | user_id=%s reel_id=%s errors=%s",
                request.user.pk,
                pk,
                serializer.errors,
            )
            return APIResponse.error(errors=serializer.errors)

        updated = serializer.save()
        logger.info("Reel updated | user_id=%s reel_id=%s", request.user.pk, pk)
        return APIResponse.success(
            data=ReelSerializer(updated, context={"request": request}).data,
            message="Reel updated successfully.",
        )

    def delete(self, request, pk):
        """Delete own reel."""
        reel = self._get_own_reel(pk, request.user)
        if not reel:
            return APIResponse.error(message="Reel not found.", status_code=404)
        reel.delete()
        logger.info("Reel deleted | user_id=%s reel_id=%s", request.user.pk, pk)
        return APIResponse.success(message="Reel deleted successfully.")


class ReelViewCountView(APIView):
    """Single endpoint for recording reel views from both sources."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        source = request.query_params.get("source", "direct")

        if source == "post":
            from .models import PostMedia

            updated = PostMedia.objects.filter(
                pk=pk,
                post__privacy=Post.Privacy.PUBLIC,
                media_type=PostMedia.MediaType.VIDEO,
            ).update(view_count=F("view_count") + 1)

            if not updated:
                return APIResponse.error(message="Media not found.", status_code=404)

        else:
            updated = Reel.objects.filter(
                pk=pk,
                privacy=Reel.Privacy.PUBLIC,
            ).update(view_count=F("view_count") + 1)

            if not updated:
                return APIResponse.error(message="Reel not found.", status_code=404)

        logger.debug(
            "Reel view counted | source=%s id=%s user_id=%s",
            source,
            pk,
            request.user.pk,
        )
        return APIResponse.success(message="View recorded.")
