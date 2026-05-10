import base64
import logging

from django.db import models
from django.db.models import Count
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from apps.utils.response import APIResponse
from .models import Post
from .serializers import PostSerializer, PostCreateSerializer, PostUpdateSerializer

logger = logging.getLogger("apps.contents")

"""Helper Functions"""

def _post_queryset():
    """Base queryset for posts."""

    return (
        Post.objects.select_related("author")
        .prefetch_related("media")
        .annotate(modia_count=Count("media"))
    )


def _encode_cursor(created_at, post_id):
    """Encode created_at + id into an opaque base64 cursor string."""
    raw = f"{created_at.isoformat()}__{post_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor_str):
    """
    Decode cursor back to (created_at, post_id).
    Returns None if cursor is missing or tampered.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor_str.encode()).decode()
        created_at_str, post_id = raw.split("__", 1)
        return created_at_str, post_id
    except Exception:
        return None


"""Post Section's Views"""

class PostListCreateView(APIView):
    """ List of Posts """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        try:
            page_size = min(int(request.query_params.get("page_size", 10)), 50)
        except (TypeError, ValueError):
            page_size = 10

        posts = _post_queryset().filter(author=request.user)

        cursor_str = request.query_params.get("cursor")
        if cursor_str:
            decoded = _decode_cursor(cursor_str)
            if not decoded:
                logger.warning(
                    "Invalid cursor supplied | user_id=%s cursor=%s",
                    request.user.pk,
                    cursor_str,
                )
                return APIResponse.error(
                    errors={"cursor": "Invalid or tampered cursor."},
                    status_code=400,
                )
            created_at_str, post_id = decoded
            # Fetch posts older than the cursor position.
            # The compound filter mirrors the composite index exactly.
            posts = posts.filter(
                models.Q(created_at__lt=created_at_str)
                | models.Q(created_at=created_at_str, id__lt=post_id)
            )

        # Fetch one extra to know if there's a next page without a COUNT query
        posts = posts.order_by("-created_at", "-id")[: page_size + 1]
        post_list = list(posts)

        has_more = len(post_list) > page_size
        if has_more:
            post_list = post_list[:page_size]  # trim the extra item

        next_cursor = None
        if has_more:
            last = post_list[-1]
            next_cursor = _encode_cursor(last.created_at, last.id)

        logger.debug(
            "Post feed fetched | user_id=%s page_size=%s has_more=%s",
            request.user.pk,
            page_size,
            has_more,
        )
        return APIResponse.success(
            data=PostSerializer(
                post_list, many=True, context={"request": request}
            ).data,
            meta={
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": page_size,
            },
        )

    def post(self, request):
        files = request.FILES.getlist("files")
        data = {"caption": request.data.get("caption", ""), "uploaded_files": files}

        serializer = PostCreateSerializer(data=data)
        if not serializer.is_valid():
            logger.warning(
                "Post creation failed | user_id=%s errors=%s",
                request.user.pk,
                serializer.errors,
            )
            return APIResponse.error(
                errors=serializer.errors, message="Post creation failed."
            )

        post = serializer.save(author=request.user)
        logger.info(
            "Post created | user_id=%s post_id=%s media_count=%s",
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
    """ Create a New Post Section """
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
        """Update a post. All fields are optional - send only what changed."""
        post = self._get_own_post(pk, request.user)
        if not post:
            return APIResponse.error(message="Post not found.", status_code=404)

        # Parse remove_media_ids from multipart form (comes as repeated field or comma-separated)
        remove_ids = request.data.getlist("remove_media_ids")
        add_files = request.FILES.getlist("add_files")

        data = {
            "caption": request.data.get("caption", post.caption),
            "remove_media_ids": remove_ids,
            "add_files": add_files,
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

        updated_post = serializer.save()
        logger.info(
            "Post updated | user_id=%s post_id=%s added=%s removed=%s",
            request.user.pk,
            pk,
            len(add_files),
            len(remove_ids),
        )

        updated_post = _post_queryset().get(pk=updated_post.pk)
        return APIResponse.success(
            data=PostSerializer(updated_post, context={"request": request}).data,
            message="Post updated successfully.",
        )

    def delete(self, request, pk):
        post = self._get_own_post(pk, request.user)
        if not post:
            return APIResponse.error(message="Post not found.", status_code=404)

        post.delete()
        logger.info("Post deleted | user_id=%s post_id=%s", request.user.pk, pk)
        return APIResponse.success(message="Post deleted successfully.")
