import logging
from django.core.cache import cache
from django.db.models import Count, Q, Subquery, OuterRef
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from apps.utils.media import compress_image
from apps.utils.response import APIResponse
from apps.contents.views import _encode_cursor, _decode_cursor, _apply_cursor
from .models import (
    Conversation,
    ConversationParticipant,
    Message,
    MessageMedia,
    MessageReaction,
    MessageStatus,
)
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    MessageReactionDetailSerializer,
    MediaUploadSerializer,
    MessageMediaSerializer,
    resolve_media_type,
)

logger = logging.getLogger("apps.chat")
PAGE_SIZE = 20


""" Query helpers """


def _conv_qs(user):
    """Annotated conversation queryset for the chat list."""
    unread_subq = (
        Message.objects.filter(conversation=OuterRef("pk"))
        .exclude(sender=user)
        .filter(statuses__recipient=user, statuses__is_read=False)
        .values("conversation")
        .annotate(c=Count("id"))
        .values("c")
    )
    return (
        Conversation.objects.filter(participants__user=user)
        .select_related("last_message__sender", "community")
        .prefetch_related("participants__user")
        .annotate(
            unread_count=Subquery(unread_subq),
            participant_count=Count("participants", distinct=True),
        )
        .order_by("-last_activity")
    )


def _msg_qs(conv):
    """Annotated message queryset for a conversation."""
    return (
        Message.objects.filter(conversation=conv)
        .select_related("sender", "reply_to__sender")
        .prefetch_related("media", "reactions")
        .annotate(
            read_by_count=Count(
                "statuses__recipient",
                filter=Q(statuses__is_read=True),
                distinct=True,
            )
        )
        .order_by("-created_at", "-id")
    )


def _get_or_create_dm(user_a, user_b):
    """Get existing DM or create new one between two users."""
    existing = (
        Conversation.objects.filter(type=Conversation.Type.DM)
        .filter(participants__user=user_a)
        .filter(participants__user=user_b)
        .first()
    )
    if existing:
        return existing, False
    conv = Conversation.objects.create(type=Conversation.Type.DM)
    ConversationParticipant.objects.bulk_create(
        [
            ConversationParticipant(conversation=conv, user=user_a),
            ConversationParticipant(conversation=conv, user=user_b),
        ]
    )
    return conv, True


def _mark_read_bulk(messages, user):
    """Bulk mark messages as read for DM conversations."""
    ids = [m.id for m in messages if m.sender_id != user.id]
    if ids:
        MessageStatus.objects.filter(
            message_id__in=ids, recipient=user, is_read=False
        ).update(is_read=True, is_delivered=True, read_at=timezone.now())


def _search_central(query, request):
    """Search central ERP employee directory."""
    import requests as req

    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    try:
        resp = req.get(
            "https://erp.betopiagroup.com/employee-directory/",
            params={"search": query},
            headers={"Authorization": f"Bearer {token}"},
            cookies={"session_id": request.COOKIES.get("session_id", "")},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("employees", [])
        logger.warning("Central search failed | status=%s", resp.status_code)
    except Exception as e:
        logger.error("Central search error | %s", e)
    return []


""" Views Section """


class UserSearchView(APIView):
    """
    Search employees from central ERP directory.
    Matches employee_code with local employee_id to flag social status.
    Results cached 30s to avoid hammering central ERP.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return APIResponse.error(
                message="Query must be at least 2 characters.", status_code=400
            )

        from django.contrib.auth import get_user_model

        User = get_user_model()

        cache_key = f"central_search:{query}"
        employees = cache.get(cache_key)
        if employees is None:
            employees = _search_central(query, request)
            cache.set(cache_key, employees, 30)

        results = []
        for emp in employees:
            emp_code = str(emp.get("employee_code", "")).strip()
            if emp_code == str(request.user.employee_id).strip():
                continue  # skip self

            local = User.objects.filter(employee_id=emp_code).first()
            results.append(
                {
                    "id": local.id if local else None,
                    "employee_id": emp_code,
                    "name": emp.get("name", ""),
                    "position": emp.get("job_title", ""),
                    "avatar_url": emp.get("avatar_url"),
                    "is_active_on_social": bool(local),
                }
            )

        return APIResponse.success(data=results)


class ConversationListView(APIView):
    """
    GET - full chat list ordered by last activity.
    POST - start or retrieve a DM. Body: { user_id }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _conv_qs(request.user)
        return APIResponse.success(
            data=ConversationSerializer(
                qs, many=True, context={"request": request}
            ).data
        )

    def post(self, request):
        from django.contrib.auth import get_user_model

        target_id = request.data.get("user_id")
        if not target_id:
            return APIResponse.error(message="user_id required.", status_code=400)

        try:
            target = get_user_model().objects.get(pk=target_id)
        except get_user_model().DoesNotExist:
            return APIResponse.error(
                message="User not found or not yet active on social.", status_code=404
            )

        if target == request.user:
            return APIResponse.error(
                message="Cannot message yourself.", status_code=400
            )

        conv, created = _get_or_create_dm(request.user, target)
        serializer = ConversationSerializer(
            _conv_qs(request.user).get(pk=conv.pk),
            context={"request": request},
        )
        return APIResponse.success(
            data=serializer.data, status_code=201 if created else 200
        )


class ConversationParticipantsView(APIView):
    """GET - list all participants in a conversation with online status."""

    permission_classes = [IsAuthenticated]

    def get(self, request, conv_id):
        if not ConversationParticipant.objects.filter(
            conversation_id=conv_id, user=request.user
        ).exists():
            return APIResponse.error(message="Conversation not found.", status_code=404)

        participants = (
            ConversationParticipant.objects.filter(conversation_id=conv_id)
            .select_related("user")
            .order_by("user__name")
        )
        return APIResponse.success(
            data=[
                {
                    "id": p.user.id,
                    "name": p.user.name,
                    "avatar_url": p.user.avatar_url,
                    "is_online": p.user.is_online,
                    "last_seen": p.user.last_seen,
                }
                for p in participants
            ]
        )


class MessageListView(APIView):
    """
    GET  - cursor-paginated message history, newest first. Auto-marks read.
    POST - upload media/doc files (text messages go via WebSocket).
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def _get_conv(self, conv_id, user):
        return Conversation.objects.filter(pk=conv_id, participants__user=user).first()

    def get(self, request, conv_id):
        conv = self._get_conv(conv_id, request.user)
        if not conv:
            return APIResponse.error(message="Conversation not found.", status_code=404)

        qs = _msg_qs(conv)
        cursor = request.query_params.get("cursor")
        if cursor:
            qs, err = _apply_cursor(qs, cursor)
            if err:
                return APIResponse.error(errors={"cursor": err}, status_code=400)

        items = list(qs[: PAGE_SIZE + 1])
        has_more = len(items) > PAGE_SIZE
        if has_more:
            items = items[:PAGE_SIZE]

        _mark_read_bulk(items, request.user)

        return APIResponse.success(
            data=MessageSerializer(items, many=True, context={"request": request}).data,
            meta={
                "next_cursor": (
                    _encode_cursor(items[-1].created_at, items[-1].id)
                    if has_more
                    else None
                ),
                "has_more": has_more,
            },
        )

    def post(self, request, conv_id):
        """Upload media/doc files. After 201, client sends media_sent via WebSocket."""
        conv = self._get_conv(conv_id, request.user)
        if not conv:
            return APIResponse.error(message="Conversation not found.", status_code=404)

        serializer = MediaUploadSerializer(
            data={
                "files": request.FILES.getlist("files"),
                "body": request.data.get("body", ""),
                "reply_to_id": request.data.get("reply_to_id"),
            }
        )
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)

        vd = serializer.validated_data
        files = vd["files"]
        types = [resolve_media_type(f)[0] for f in files]
        msg_type = (
            Message.Type.DOC
            if all(t == MessageMedia.MediaType.DOC for t in types)
            else Message.Type.MEDIA
        )

        msg = Message.objects.create(
            conversation=conv,
            sender=request.user,
            type=msg_type,
            body=vd["body"],
            reply_to_id=vd.get("reply_to_id"),
        )

        MessageMedia.objects.bulk_create(
            [
                MessageMedia(
                    message=msg,
                    file=(
                        compress_image(f)
                        if resolve_media_type(f)[0] == MessageMedia.MediaType.IMAGE
                        else f
                    ),
                    media_type=resolve_media_type(f)[0],
                    file_name=f.name,
                    file_size=f.size,
                    order=i,
                )
                for i, f in enumerate(files)
            ]
        )

        # Status rows only for DM
        if conv.type == Conversation.Type.DM:
            other_ids = (
                ConversationParticipant.objects.filter(conversation=conv)
                .exclude(user=request.user)
                .values_list("user_id", flat=True)
            )
            MessageStatus.objects.bulk_create(
                [MessageStatus(message=msg, recipient_id=uid) for uid in other_ids]
            )

        Conversation.objects.filter(pk=conv.pk).update(
            last_message=msg, last_activity=timezone.now()
        )

        msg = _msg_qs(conv).get(pk=msg.pk)
        logger.info(
            "Media sent | user=%s conv=%s files=%s",
            request.user.pk,
            conv_id,
            len(files),
        )
        return APIResponse.success(
            data=MessageSerializer(msg, context={"request": request}).data,
            status_code=201,
        )


class MessageReactionListView(APIView):
    """
    GET - list all reactors on a message.
    Supports ?reaction=love filter to show one type (like WhatsApp reaction sheet).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, conv_id, msg_id):
        if not ConversationParticipant.objects.filter(
            conversation_id=conv_id, user=request.user
        ).exists():
            return APIResponse.error(message="Conversation not found.", status_code=404)

        qs = (
            MessageReaction.objects.filter(message_id=msg_id)
            .select_related("user")
            .order_by("reaction", "created_at")
        )

        reaction_filter = request.query_params.get("reaction", "").lower()
        if reaction_filter:
            if reaction_filter not in MessageReaction.Reaction.values:
                return APIResponse.error(
                    errors={
                        "reaction": f"Choose from: {', '.join(MessageReaction.Reaction.values)}"
                    },
                    status_code=400,
                )
            qs = qs.filter(reaction=reaction_filter)

        counts = {
            r["reaction"]: r["count"]
            for r in MessageReaction.objects.filter(message_id=msg_id)
            .values("reaction")
            .annotate(count=Count("id"))
        }
        return APIResponse.success(
            data=MessageReactionDetailSerializer(qs, many=True).data,
            meta={"counts": counts, "total": sum(counts.values())},
        )


class ConversationMediaView(APIView):
    """GET - shared media gallery (images + videos) for a conversation."""

    permission_classes = [IsAuthenticated]

    def get(self, request, conv_id):
        if not ConversationParticipant.objects.filter(
            conversation_id=conv_id, user=request.user
        ).exists():
            return APIResponse.error(message="Conversation not found.", status_code=404)

        media = (
            MessageMedia.objects.filter(
                message__conversation_id=conv_id,
                message__is_deleted=False,
                media_type__in=[
                    MessageMedia.MediaType.IMAGE,
                    MessageMedia.MediaType.VIDEO,
                ],
            )
            .select_related("message__sender")
            .order_by("-created_at")
        )
        return APIResponse.success(
            data=MessageMediaSerializer(
                media, many=True, context={"request": request}
            ).data
        )
