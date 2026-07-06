import base64
import logging
from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from django.db.models import CharField, Count, OuterRef, Subquery
from django.utils import timezone
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.interactions.models import Like
from apps.utils.response import APIResponse
from apps.utils.throttles import UploadThrottle

from .models import Story, StoryTrayState, StoryView
from .serializers import (
    StoryCreateSerializer,
    StorySerializer,
    story_preview_url,
)
from .tasks import generate_story_thumbnail_task

logger = logging.getLogger("apps.story")


def _encode_cursor(created_at, obj_id):
    raw = f"{created_at.isoformat()}__{obj_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor_str):
    try:
        raw = base64.urlsafe_b64decode(cursor_str.encode()).decode()
        created_at_str, obj_id = raw.split("__", 1)
        return created_at_str, obj_id
    except Exception:
        return None, None


def _apply_cursor(queryset, cursor_str):
    from django.db.models import Q

    created_at_str, obj_id = _decode_cursor(cursor_str)
    if not created_at_str:
        return queryset, "Invalid or tampered cursor."
    return (
        queryset.filter(
            Q(created_at__lt=created_at_str)
            | Q(created_at=created_at_str, id__lt=obj_id)
        ),
        None,
    )


def _paginate_cursor(queryset, page_size):
    items = list(queryset[: page_size + 1])
    has_more = len(items) > page_size
    if has_more:
        items = items[:page_size]
    next_cursor = (
        _encode_cursor(items[-1].created_at, items[-1].id) if has_more else None
    )
    return items, has_more, next_cursor


def _story_content_type():
    return ContentType.objects.get_for_model(Story)


def _annotate_stories(qs, user, *, include_stats=True):
    ct = _story_content_type()
    annotations = {
        "user_reaction": Subquery(
            Like.objects.filter(
                content_type=ct,
                object_id=OuterRef("pk"),
                user=user,
            ).values("reaction")[:1],
            output_field=CharField(),
        ),
    }
    if include_stats:
        annotations["like_count"] = Count("likes", distinct=True)
        annotations["viewer_count"] = Count("views", distinct=True)
    return qs.annotate(**annotations)


def _attach_top_reacts(items):
    if not items:
        return items

    ct = _story_content_type()
    object_ids = [item.id for item in items]
    react_map = defaultdict(list)
    rows = (
        Like.objects.filter(content_type=ct, object_id__in=object_ids)
        .values("object_id", "reaction")
        .annotate(count=Count("id"))
        .order_by("object_id", "-count")
    )
    for row in rows:
        react_map[row["object_id"]].append(row["reaction"])

    for item in items:
        item.top_reacts = react_map.get(item.id, [])[:3]
    return items


def _active_qs():
    return Story.objects.filter(expires_at__gt=timezone.now())


def _serialize_story_list(
    stories, request, viewed_ids=None, *, with_stats=True, include_preview_url=True
):
    viewed_ids = viewed_ids or set()
    if with_stats:
        _attach_top_reacts(stories)
    context = {"request": request, "include_preview_url": include_preview_url}
    data = []
    for story in stories:
        story.is_viewed = story.id in viewed_ids
        if not with_stats:
            story.like_count = 0
            story.viewer_count = 0
            story.top_reacts = []
        data.append(StorySerializer(story, context=context).data)
    return data


class StoryTrayView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()
        active = list(
            _active_qs()
            .select_related("author")
            .only(
                "id",
                "author_id",
                "file",
                "thumbnail",
                "media_type",
                "created_at",
                "expires_at",
                "author__id",
                "author__name",
                "author__avatar_url",
            )
            .order_by("author_id", "created_at")
        )

        viewed_ids = set(
            StoryView.objects.filter(
                viewer=user,
                story__expires_at__gt=now,
            ).values_list("story_id", flat=True)
        )
        tray_states = {
            row["author_id"]: row["last_viewed_at"]
            for row in StoryTrayState.objects.filter(viewer=user).values(
                "author_id", "last_viewed_at"
            )
        }

        by_author = defaultdict(list)
        for story in active:
            by_author[story.author_id].append(story)

        tray_items = []
        for author_id, stories in by_author.items():
            if author_id == user.id:
                continue
            latest = stories[-1]
            has_unseen = any(s.id not in viewed_ids for s in stories)
            tray_items.append(
                {
                    "user": {
                        "id": str(latest.author.id),
                        "name": latest.author.name,
                        "avatar_url": latest.author.avatar_url or "",
                    },
                    "has_unseen": has_unseen,
                    "item_count": len(stories),
                    "preview_url": story_preview_url(latest, request),
                    "latest_created": latest.created_at,
                    "last_viewed_at": tray_states.get(author_id),
                }
            )

        tray_items.sort(
            key=lambda item: (
                0 if item["has_unseen"] else 1,
                -item["latest_created"].timestamp()
                if item["has_unseen"]
                else (item["last_viewed_at"].timestamp() if item["last_viewed_at"] else 0),
            )
        )

        my_stories = by_author.get(user.id, [])
        my_story = None
        if my_stories:
            latest = my_stories[-1]
            my_story = {
                "item_count": len(my_stories),
                "has_unseen": any(s.id not in viewed_ids for s in my_stories),
                "preview_url": story_preview_url(latest, request),
            }

        return APIResponse.success(
            data={
                "my_story": my_story,
                "stories": [
                    {
                        "user": item["user"],
                        "has_unseen": item["has_unseen"],
                        "item_count": item["item_count"],
                        "preview_url": item["preview_url"],
                    }
                    for item in tray_items
                ],
            }
        )


class StoryUserCarouselView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        is_owner = str(user_id) == str(request.user.id)
        stories = list(
            _annotate_stories(
                _active_qs().filter(author_id=user_id),
                request.user,
                include_stats=is_owner,
            ).order_by("created_at", "id")
        )
        if not stories:
            return APIResponse.error(message="No active stories found.", status_code=404)

        viewed_ids = set(
            StoryView.objects.filter(
                viewer=request.user,
                story_id__in=[s.id for s in stories],
            ).values_list("story_id", flat=True)
        )
        return APIResponse.success(
            data=_serialize_story_list(
                stories,
                request,
                viewed_ids,
                with_stats=is_owner,
                include_preview_url=False,
            )
        )


class StoryCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [UploadThrottle]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = StoryCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return APIResponse.error(
                errors=serializer.errors,
                message="Story upload failed.",
            )

        story = serializer.save()
        if story.media_type == Story.MediaType.VIDEO:
            try:
                generate_story_thumbnail_task.delay(str(story.pk))
            except Exception as exc:
                logger.error(
                    "Thumbnail task queue failed | story_id=%s error=%s",
                    story.pk,
                    exc,
                )

        story = _annotate_stories(Story.objects.filter(pk=story.pk), request.user).first()
        story.top_reacts = []
        story.is_viewed = False
        return APIResponse.success(
            data=StorySerializer(story, context={"request": request}).data,
            message="Story created successfully.",
            status_code=201,
        )


class StoryViewMarkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            story = _active_qs().get(pk=pk)
        except Story.DoesNotExist:
            return APIResponse.error(message="Story not found.", status_code=404)

        StoryView.objects.update_or_create(
            story=story,
            viewer=request.user,
            defaults={"viewed_at": timezone.now()},
        )

        active_ids = list(
            _active_qs()
            .filter(author_id=story.author_id)
            .values_list("id", flat=True)
        )
        viewed_count = StoryView.objects.filter(
            viewer=request.user,
            story_id__in=active_ids,
        ).count()
        if viewed_count == len(active_ids):
            StoryTrayState.objects.update_or_create(
                viewer=request.user,
                author_id=story.author_id,
                defaults={"last_viewed_at": timezone.now()},
            )

        return APIResponse.success(data={"viewed": True})


class StoryDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            story = Story.objects.get(pk=pk, author=request.user)
        except Story.DoesNotExist:
            return APIResponse.error(message="Story not found.", status_code=404)

        if story.file:
            story.file.delete(save=False)
        if story.thumbnail:
            story.thumbnail.delete(save=False)
        story.delete()
        return APIResponse.success(message="Story deleted successfully.")


class StoryMineView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            page_size = min(int(request.query_params.get("page_size", 20)), 50)
        except (TypeError, ValueError):
            page_size = 20

        qs = _annotate_stories(
            Story.objects.filter(author=request.user),
            request.user,
        ).order_by("-created_at", "-id")

        cursor = request.query_params.get("cursor")
        if cursor:
            qs, err = _apply_cursor(qs, cursor)
            if err:
                return APIResponse.error(errors={"cursor": err}, status_code=400)

        items, has_more, next_cursor = _paginate_cursor(qs, page_size)
        _attach_top_reacts(items)
        for item in items:
            item.is_viewed = True

        return APIResponse.success(
            data=StorySerializer(items, many=True, context={"request": request}).data,
            meta={
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": page_size,
            },
        )


class StoryViewersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            story = Story.objects.select_related("author").get(pk=pk)
        except Story.DoesNotExist:
            return APIResponse.error(message="Story not found.", status_code=404)

        if story.author_id != request.user.id:
            return APIResponse.error(message="Not allowed.", status_code=403)

        try:
            page = max(int(request.query_params.get("page", 1)), 1)
            page_size = min(int(request.query_params.get("page_size", 20)), 50)
        except (TypeError, ValueError):
            page, page_size = 1, 20

        qs = (
            StoryView.objects.filter(story=story)
            .select_related("viewer")
            .order_by("-viewed_at")
        )
        total = qs.count()
        offset = (page - 1) * page_size
        views = qs[offset : offset + page_size]

        data = [
            {
                "user_id": view.viewer.id,
                "name": view.viewer.name,
                "avatar_url": view.viewer.avatar_url,
                "viewed_at": view.viewed_at,
            }
            for view in views
        ]
        return APIResponse.success(
            data=data,
            meta={
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": -(-total // page_size) if total else 0,
            },
        )
