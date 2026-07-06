import base64
import logging
from django.conf import settings

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Count, F, Prefetch, Exists, OuterRef

from apps.utils.throttles import UploadThrottle, FeedThrottle

from django.contrib.contenttypes.models import ContentType
from apps.interactions.models import Like

from django.db.models import Subquery, CharField
from django.db.models.functions import Coalesce
from django.db.models import Value

from apps.utils.response import APIResponse
from .models import (
    Post,
    PostMedia,
    Reel,
    Community,
    CommunityMember,
    ReelView,
    SavedItem,
)
from .serializers import (
    PostSerializer,
    PostCreateSerializer,
    PostUpdateSerializer,
    ReelSerializer,
    ReelCreateSerializer,
    ReelUpdateSerializer,
)

from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger("apps.contents")


""" HELPER FUNCTIONS """


def _user_reaction_subquery(content_type, user):
    """
    Returns the user's reaction string for each object.
    Returns None if user has not reacted.
    Used instead of boolean is_liked.
    """
    return Subquery(
        Like.objects.filter(
            content_type=content_type,
            object_id=OuterRef("pk"),
            user=user,
        ).values("reaction")[:1],
        output_field=CharField(),
    )


def _top_reacts_subquery(content_type):
    """
    Returns top 3 reaction types ordered by count descending.
    Built in Python after fetching - Django ORM can't return
    ordered arrays as a subquery cleanly.
    Handled in _attach_top_reacts() instead.
    """
    pass  # see _attach_top_reacts below


def _attach_top_reacts(items, content_type):
    """
    Attach top_reacts to a list of Post/Reel/PostMedia objects.
    Fetches all reactions for all items in 1 query - no N+1.
    Returns top 3 reaction types ordered by count desc per item.
    """
    from apps.interactions.models import Like
    from django.db.models import Count

    if not items:
        return items

    object_ids = [item.id for item in items]

    # Single query - all reaction counts for all items
    reaction_data = (
        Like.objects.filter(content_type=content_type, object_id__in=object_ids)
        .values("object_id", "reaction")
        .annotate(count=Count("id"))
        .order_by("object_id", "-count")
    )

    # Group by object_id
    from collections import defaultdict

    react_map = defaultdict(list)
    for row in reaction_data:
        react_map[row["object_id"]].append(row["reaction"])

    # Attach top 3 to each item
    for item in items:
        item.top_reacts = react_map.get(item.id, [])[:3]

    return items


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


def _post_queryset(user=None):

    qs = (
        Post.objects.select_related("author", "community")
        .prefetch_related(Prefetch("media", queryset=_annotated_media_qs(user)))
        .annotate(
            media_count=Count("media", distinct=True),
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
        )
        .order_by("-created_at", "-id")
    )

    if user:
        post_ct = ContentType.objects.get_for_model(Post)
        qs = qs.annotate(
            user_reaction=_user_reaction_subquery(post_ct, user),
            is_saved=Exists(
                SavedItem.objects.filter(
                    content_type=post_ct,
                    object_id=OuterRef("pk"),
                    user=user,
                )
            ),
        )
    return qs


def _reel_queryset(user=None):

    qs = (
        Reel.objects.select_related("author")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
        )
        .order_by("-created_at", "-id")
    )

    if user:
        reel_ct = ContentType.objects.get_for_model(Reel)
        qs = qs.annotate(
            user_reaction=_user_reaction_subquery(reel_ct, user),
            is_saved=Exists(
                SavedItem.objects.filter(
                    content_type=reel_ct,
                    object_id=OuterRef("pk"),
                    user=user,
                )
            ),
        )
    return qs


def _parse_page_size(request, default=10):
    try:
        return min(int(request.query_params.get("page_size", default)), 50)
    except (TypeError, ValueError):
        return default


def _annotated_media_qs(user=None):
    from django.contrib.contenttypes.models import ContentType
    from apps.interactions.models import Like

    qs = PostMedia.objects.annotate(
        like_count=Count("likes", distinct=True),
        comment_count=Count("comments", distinct=True),
    ).order_by("order")

    if user:
        media_ct = ContentType.objects.get_for_model(PostMedia)
        qs = qs.annotate(user_reaction=_user_reaction_subquery(media_ct, user))
    return qs


def _get_community(community_id, user):
    """
    Validate community_id passed as ?community=<uuid> query param.

    Rules:
      - If no community_id given - returns (None, None), post is a regular post
      - Community must exist and be active
      - User must be a member of that community to post in it

    Returns (Community instance | None, error message | None).
    """
    if not community_id:
        return None, None
    try:
        community = Community.objects.get(pk=community_id, is_active=True)
    except Community.DoesNotExist:
        return None, "Community not found."
    if not CommunityMember.objects.filter(community=community, user=user).exists():
        return None, "You are not a member of this community."
    return community, None


""" POST SECTION VIEWS"""


class PostListCreateView(APIView):
    """List and Create Own Posts."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [UploadThrottle]

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

        community_id = request.query_params.get("community")
        community, error = _get_community(community_id, request.user)
        if error:
            return APIResponse.error(
                message=error, status_code=400 if "not found" in error else 403
            )
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

        post = serializer.save(author=request.user, community=community)

        from apps.feed.notify import notify_post_created
        from apps.feed.views import invalidate_user_feed, invalidate_community_feed

        notify_post_created(post, request.user.pk)
        invalidate_user_feed(request.user.pk)
        if community:
            invalidate_community_feed(community.pk)

        logger.info(
            "Post created | user_id=%s post_id=%s media=%s community=%s",
            request.user.pk,
            post.pk,
            len(files),
            community.name if community else None,
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

        from apps.feed.notify import notify_reel_created

        notify_reel_created(reel, request.user.pk)
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
        max_views = getattr(settings, "REEL_MAX_VIEWS_PER_USER", 5)

        if source == "post":
            model = PostMedia
            try:
                PostMedia.objects.get(
                    pk=pk,
                    media_type=PostMedia.MediaType.VIDEO,
                )
            except PostMedia.DoesNotExist:
                return APIResponse.error(message="Media not found.", status_code=404)
        else:
            model = Reel
            try:
                Reel.objects.get(pk=pk)
            except Reel.DoesNotExist:
                return APIResponse.error(message="Reel not found.", status_code=404)

        content_type = ContentType.objects.get_for_model(model)

        # Get or create user's view record for this video
        reel_view, created = ReelView.objects.get_or_create(
            user=request.user,
            content_type=content_type,
            object_id=pk,
            defaults={"view_count": 0},
        )

        if reel_view.view_count >= max_views:
            # User has already hit the limit - return silently
            logger.debug(
                "View limit reached | source=%s id=%s user_id=%s count=%s max=%s",
                source,
                pk,
                request.user.pk,
                reel_view.view_count,
                max_views,
            )
            return APIResponse.success(message="View recorded.")

        # Increment user's personal view count atomically
        ReelView.objects.filter(pk=reel_view.pk).update(view_count=F("view_count") + 1)

        # Increment the actual video's view count atomically
        model.objects.filter(pk=pk).update(view_count=F("view_count") + 1)

        logger.debug(
            "View counted | source=%s id=%s user_id=%s",
            source,
            pk,
            request.user.pk,
        )
        return APIResponse.success(message="View recorded.")


""" COMMUNITY SECTION VIEWS """


class CommunityListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        communities = (
            Community.objects.filter(members__user=request.user, is_active=True)
            .annotate(member_count=Count("members"))
            .distinct()
        )
        from .serializers import CommunitySerializer

        return APIResponse.success(
            data=CommunitySerializer(
                communities, many=True, context={"request": request}
            ).data
        )


class CommunityMemberListView(APIView):
    """
    Returns paginated list of members for a community.
    Only accessible to members of that community.

    Response per member: central_id, name, avatar_url only.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        # Only members can see the member list
        if not CommunityMember.objects.filter(
            user=request.user, community_id=community_id
        ).exists():
            return APIResponse.error(message="Community not found.", status_code=404)

        try:
            page_size = min(int(request.query_params.get("page_size", 20)), 50)
            page = max(int(request.query_params.get("page", 1)), 1)
        except (TypeError, ValueError):
            page_size, page = 20, 1

        members = (
            CommunityMember.objects.filter(community_id=community_id)
            .select_related("user")
            .order_by("user__name")
        )

        total = members.count()
        offset = (page - 1) * page_size
        items = members[offset : offset + page_size]

        data = [
            {
                "id": m.user.id,
                "employee_id": m.user.employee_id,
                "name": m.user.name,
                "position": m.user.position,
                "avatar_url": m.user.avatar_url,
            }
            for m in items
        ]

        return APIResponse.success(
            data=data,
            meta={
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": -(-total // page_size),
            },
        )


class SaveToggleView(APIView):
    """Toggle save on any post, reel or post video"""

    permission_classes = [IsAuthenticated]

    TARGET_MAP = {
        "post": Post,
        "reel": Reel,
        "post_video": PostMedia,
    }

    def post(self, request, target_type, pk):
        model = self.TARGET_MAP.get(target_type)
        if not model:
            return APIResponse.error(
                error={
                    "target_type": f"Invalid Type '{target_type}'. User post, reel or post_video."
                },
                status_code=400,
            )

        if not model.objects.filter(pk=pk).exists():
            return APIResponse.error(message="Not found", status_code=400)

        content_type = ContentType.objects.get_for_model(model)

        saved_item, created = SavedItem.objects.get_or_create(
            user=request.user,
            content_type=content_type,
            object_id=pk,
        )

        if not created:
            saved_item.delete()
            saved = False
        else:
            saved = True

        logger.info(
            "Save toggled | user_id=%s target=%s pk=%s saved=%s",
            request.user.pk,
            target_type,
            pk,
            saved,
        )
        from apps.feed.views import invalidate_user_feed
        invalidate_user_feed(request.user.pk)

        return APIResponse.success(
            data={"saved": saved},
            message="Saved." if saved else "Unsaved.",
        )


class SavedItemListView(APIView):
    """
    Returns paginated list of the user's saved items.
    Cursor-based pagination - newest saved first.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.feed.serializers import NFFeedPostSerializer, NFFeedReelSerializer

        try:
            page_size = min(int(request.query_params.get("page_size", 10)), 50)
        except (TypeError, ValueError):
            page_size = 10

        # Optional type filter
        filter_type = request.query_params.get("type")

        # Build content type map
        post_ct = ContentType.objects.get_for_model(Post)
        reel_ct = ContentType.objects.get_for_model(Reel)
        post_media_ct = ContentType.objects.get_for_model(PostMedia)

        type_map = {
            "post": post_ct,
            # "reel" filter now covers both reel and post_video
        }

        qs = SavedItem.objects.filter(user=request.user).order_by("-created_at")

        if filter_type == "post":
            qs = qs.filter(content_type=post_ct)
        elif filter_type == "reel":
            # Filter returns both direct reels AND post videos together
            qs = qs.filter(content_type__in=[reel_ct, post_media_ct])

        # Cursor pagination
        cursor_str = request.query_params.get("cursor")
        if cursor_str:
            decoded = _decode_cursor(cursor_str)
            if not decoded:
                return APIResponse.error(
                    errors={"cursor": "Invalid cursor."}, status_code=400
                )
            created_at_str, obj_id = decoded
            from django.db.models import Q

            qs = qs.filter(
                Q(created_at__lt=created_at_str)
                | Q(created_at=created_at_str, id__lt=obj_id)
            )

        items = list(qs[: page_size + 1])
        has_more = len(items) > page_size
        if has_more:
            items = items[:page_size]

        next_cursor = (
            _encode_cursor(items[-1].created_at, items[-1].id) if has_more else None
        )

        # Collect all IDs per type for bulk fetching
        post_ids = [i.object_id for i in items if i.content_type_id == post_ct.id]
        reel_ids = [i.object_id for i in items if i.content_type_id == reel_ct.id]
        post_video_ids = [
            i.object_id for i in items if i.content_type_id == post_media_ct.id
        ]

        # Fetch actual objects in bulk - no N+1
        posts = (
            {p.id: p for p in _post_queryset(request.user).filter(id__in=post_ids)}
            if post_ids
            else {}
        )

        reels = (
            {r.id: r for r in _reel_queryset(request.user).filter(id__in=reel_ids)}
            if reel_ids
            else {}
        )

        from django.db.models import Count, Exists, OuterRef
        from apps.interactions.models import Like

        post_videos = {}
        if post_video_ids:
            media_ct = ContentType.objects.get_for_model(PostMedia)
            pv_qs = (
                PostMedia.objects.filter(
                    id__in=post_video_ids,
                    media_type=PostMedia.MediaType.VIDEO,
                )
                .select_related("post__author", "post__community")
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
            )
            post_videos = {pv.id: pv for pv in pv_qs}

        # Build unified response preserving saved order
        result = []
        for item in items:
            ct_id = item.content_type_id
            oid = item.object_id

            if ct_id == post_ct.id and oid in posts:
                post = posts[oid]
                result.append(
                    {
                        "type": "post",
                        "saved_at": item.created_at,
                        "data": NFFeedPostSerializer(
                            post, context={"request": request}
                        ).data,
                    }
                )

            elif ct_id == reel_ct.id and oid in reels:
                reel = reels[oid]
                result.append(
                    {
                        "type": "reel",  # direct reel
                        "source": "direct",
                        "saved_at": item.created_at,
                        "data": ReelSerializer(reel, context={"request": request}).data,
                    }
                )

            elif ct_id == post_media_ct.id and oid in post_videos:
                pm = post_videos[oid]
                result.append(
                    {
                        "type": "reel",  # post video - same type as direct reel
                        "source": "post",  # Flutter uses source to differentiate if needed
                        "saved_at": item.created_at,
                        "data": {
                            "id": pm.id,
                            "source": "post",
                            "author": {
                                "id": pm.post.author.id,
                                "central_id": pm.post.author.central_id,
                                "name": pm.post.author.name,
                                "avatar_url": pm.post.author.avatar_url,
                            },
                            "caption": pm.caption,
                            "video_url": request.build_absolute_uri(pm.file.url),
                            "like_count": pm.like_count,
                            "comment_count": pm.comment_count,
                            "is_liked": pm.is_liked,
                            "view_count": pm.view_count,
                            "community": (
                                pm.post.community.name if pm.post.community else None
                            ),
                        },
                    }
                )
        logger.debug(
            "Saved list | user_id=%s page_size=%s has_more=%s",
            request.user.pk,
            page_size,
            has_more,
        )
        return APIResponse.success(
            data=result,
            meta={
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": page_size,
            },
        )
