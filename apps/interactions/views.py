import base64
import logging

from django.contrib.contenttypes.models import ContentType
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.utils.throttles import InteractionThrottle

from apps.utils.response import APIResponse
from apps.contents.models import Post, PostMedia, Reel
from .models import Like, Comment
from .serializers import (
    LikerSerializer,
    CommentSerializer,
    CommentCreateSerializer,
    CommentUpdateSerializer,
)

logger = logging.getLogger("apps.interactions")

TARGET_MODEL_MAP = {
    "post": Post,
    "media": PostMedia,
    "reel": Reel,
}


def _get_content_type(target_type):
    model = TARGET_MODEL_MAP.get(target_type)
    if not model:
        return None, None
    return ContentType.objects.get_for_model(model), model


""" Cursor helpers """


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


def _parse_page_size(request, default=20):
    try:
        return min(int(request.query_params.get("page_size", default)), 50)
    except (TypeError, ValueError):
        return default


""" Tree builder """


def _build_comment_tree(comments):
    """Build nested comment tree from a flat list in O(n)."""

    comment_map = {c.id: c for c in comments}

    # Initialise _replies on every comment
    for c in comments:
        c._replies = []

    roots = []
    for c in comments:
        if c.parent_id and c.parent_id in comment_map:
            comment_map[c.parent_id]._replies.append(c)
        else:
            roots.append(c)

    return roots


""" Like views (unchanged) """


class LikeToggleView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [InteractionThrottle]

    def post(self, request, target_type, pk):
        content_type, model = _get_content_type(target_type)
        if not content_type:
            return APIResponse.error(
                errors={
                    "target_type": f"Invalid type '{target_type}'. Use post, media or reel."
                },
                status_code=400,
            )

        try:
            if target_type == "media":
                model.objects.get(pk=pk, post__privacy=Post.Privacy.PUBLIC)
            elif target_type == "post":
                model.objects.get(pk=pk, privacy=Post.Privacy.PUBLIC)
            elif target_type == "reel":
                model.objects.get(pk=pk, privacy=Reel.Privacy.PUBLIC)
        except model.DoesNotExist:
            return APIResponse.error(message="Target not found.", status_code=404)

        like, created = Like.objects.get_or_create(
            user=request.user,
            content_type=content_type,
            object_id=pk,
        )
        if not created:
            like.delete()
            liked = False
        else:
            liked = True

        like_count = Like.objects.filter(
            content_type=content_type,
            object_id=pk,
        ).count()

        logger.info(
            "Like toggled | user_id=%s target=%s pk=%s liked=%s count=%s",
            request.user.pk,
            target_type,
            pk,
            liked,
            like_count,
        )

        return APIResponse.success(
            data={"liked": liked, "like_count": like_count},
            message="Liked." if liked else "Unliked.",
        )


class LikerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, target_type, pk):
        content_type, model = _get_content_type(target_type)
        if not content_type:
            return APIResponse.error(
                errors={
                    "target_type": f"Invalid type '{target_type}'. Use post, media or reel."
                },
                status_code=400,
            )

        try:
            page_size = min(int(request.query_params.get("page_size", 20)), 50)
            page = max(int(request.query_params.get("page", 1)), 1)
        except (TypeError, ValueError):
            page_size, page = 20, 1

        likes = (
            Like.objects.filter(content_type=content_type, object_id=pk)
            .select_related("user")
            .order_by("-created_at")
        )

        total = likes.count()
        offset = (page - 1) * page_size
        items = likes[offset : offset + page_size]

        logger.debug(
            "Liker list | target=%s pk=%s total=%s",
            target_type,
            pk,
            total,
        )

        return APIResponse.success(
            data=LikerSerializer(items, many=True).data,
            meta={
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": -(-total // page_size),
            },
        )


""" Comment views """


class CommentListCreateView(APIView):
    """
    GET - returns full comment tree for a target, cursor paginated on roots.
    POST - creates a new comment or reply on a target.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [InteractionThrottle]

    def get(self, request, target_type, pk):
        content_type, model = _get_content_type(target_type)
        if not content_type:
            return APIResponse.error(
                errors={"target_type": f"Invalid type '{target_type}'."},
                status_code=400,
            )

        page_size = _parse_page_size(request)

        # Fetch ALL comments for this target in one query
        # select_related on user and parent prevents N+1
        all_comments = list(
            Comment.objects.filter(content_type=content_type, object_id=pk)
            .select_related("user", "parent")
            .order_by("created_at")  # oldest first — natural thread order
        )

        # Annotate reply_count on each comment
        from django.db.models import Count

        reply_counts = (
            Comment.objects.filter(
                content_type=content_type, object_id=pk, parent__isnull=False
            )
            .values("parent_id")
            .annotate(count=Count("id"))
        )
        reply_count_map = {str(r["parent_id"]): r["count"] for r in reply_counts}
        for c in all_comments:
            c.reply_count = reply_count_map.get(str(c.id), 0)

        # Build tree in Python — O(n), no extra DB queries
        roots = _build_comment_tree(all_comments)

        # Cursor pagination on roots only
        cursor_str = request.query_params.get("cursor")
        if cursor_str:
            decoded = _decode_cursor(cursor_str)
            if not decoded:
                return APIResponse.error(
                    errors={"cursor": "Invalid cursor."},
                    status_code=400,
                )
            created_at_str, obj_id = decoded
            roots = [
                r
                for r in roots
                if r.created_at.isoformat() < created_at_str
                or (r.created_at.isoformat() == created_at_str and str(r.id) < obj_id)
            ]

        has_more = len(roots) > page_size
        roots = roots[:page_size]

        next_cursor = (
            _encode_cursor(roots[-1].created_at, roots[-1].id) if has_more else None
        )

        logger.debug(
            "Comment list | target=%s pk=%s roots=%s",
            target_type,
            pk,
            len(roots),
        )

        return APIResponse.success(
            data=CommentSerializer(roots, many=True).data,
            meta={
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": page_size,
            },
        )

    def post(self, request, target_type, pk):
        content_type, model = _get_content_type(target_type)
        if not content_type:
            return APIResponse.error(
                errors={"target_type": f"Invalid type '{target_type}'."},
                status_code=400,
            )

        # Verify target exists
        try:
            if target_type == "media":
                model.objects.get(pk=pk, post__privacy=Post.Privacy.PUBLIC)
            elif target_type == "post":
                model.objects.get(pk=pk, privacy=Post.Privacy.PUBLIC)
            elif target_type == "reel":
                model.objects.get(pk=pk, privacy=Reel.Privacy.PUBLIC)
        except model.DoesNotExist:
            return APIResponse.error(message="Target not found.", status_code=404)

        serializer = CommentCreateSerializer(
            data=request.data,
            context={
                "content_type": content_type,
                "object_id": pk,
            },
        )
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)

        comment = serializer.save(
            user=request.user,
            content_type=content_type,
            object_id=pk,
        )
        comment.reply_count = 0
        comment._replies = []

        logger.info(
            "Comment created | user_id=%s target=%s pk=%s comment_id=%s parent=%s",
            request.user.pk,
            target_type,
            pk,
            comment.pk,
            comment.parent_id,
        )

        return APIResponse.success(
            data=CommentSerializer(comment).data,
            message="Comment posted.",
            status_code=201,
        )


class CommentDetailView(APIView):
    """Retrieve, update or delete a single comment. Only the author can update or delete."""

    permission_classes = [IsAuthenticated]

    def _get_own_comment(self, comment_id, user):
        try:
            return Comment.objects.get(pk=comment_id, user=user)
        except Comment.DoesNotExist:
            logger.warning(
                "Comment not found | user_id=%s comment_id=%s",
                user.pk,
                comment_id,
            )
            return None

    def patch(self, request, target_type, pk, comment_id):
        comment = self._get_own_comment(comment_id, request.user)
        if not comment:
            return APIResponse.error(message="Comment not found.", status_code=404)

        serializer = CommentUpdateSerializer(comment, data=request.data, partial=True)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)

        updated = serializer.save()
        updated.reply_count = updated.replies.count()
        updated._replies = []

        logger.info(
            "Comment updated | user_id=%s comment_id=%s",
            request.user.pk,
            comment_id,
        )

        return APIResponse.success(
            data=CommentSerializer(updated).data,
            message="Comment updated.",
        )

    def delete(self, request, target_type, pk, comment_id):
        try:
            comment = Comment.objects.get(pk=comment_id, user=request.user)
        except Comment.DoesNotExist:
            logger.warning(
                "Comment not found | user_id=%s comment_id=%s",
                request.user.pk,
                comment_id,
            )
            return APIResponse.error(message="Comment not found.", status_code=404)

        # deletes all nested replies at DB level
        comment.delete()
        logger.info(
            "Comment deleted | user_id=%s comment_id=%s",
            request.user.pk,
            comment_id,
        )
        return APIResponse.success(message="Comment deleted.")
