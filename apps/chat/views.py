import logging
from django.core.cache import cache
from django.db.models import Count, Q, Exists, OuterRef, Subquery
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.utils.media import compress_image
from apps.utils.response import APIResponse
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
    MessageCreateSerializer,
    MessageReactionDetailSerializer,
    ConversationParticipantSerializer,
    _resolve_media_type,
)

logger = logging.getLogger("apps.chat")
PAGE_SIZE = 20

""" Helper functions for views """


def _broadcast(conv_id, payload):
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(f"chat_{conv_id}", payload)


def _get_or_create_dm(user_a, user_b):
    existing = (
        Conversation.objects.filter(type=Conversation.ConversationType.DM)
        .filter(participants__user=user_a)
        .filter(participants__user=user_b)
        .first()
    )
    if existing:
        return existing, False
    conv = Conversation.objects.create(type=Conversation.ConversationType.DM)
    ConversationParticipant.objects.bulk_create(
        [
            ConversationParticipant(conversation=conv, user=user_a),
            ConversationParticipant(conversation=conv, user=user_b),
        ]
    )
    return conv, True


def _unread_subquery(user):
    return (
        Message.objects.filter(conversation=OuterRef("pk"))
        .exclude(sender=user)
        .filter(statuses__recipient=user, statuses__is_read=False)
        .values("conversation")
        .annotate(c=Count("id"))
        .values("c")
    )


def _conv_qs(user):
    return (
        Conversation.objects.filter(participants__user=user)
        .select_related("last_message__sender", "community")
        .prefetch_related("participants__user")
        .annotate(
            unread_count=Subquery(_unread_subquery(user)),
            participant_count=Count("participants", distinct=True),
        )
        .order_by("-last_activity")
    )


def _msg_qs(conv):
    return (
        Message.objects.filter(conversation=conv)
        .select_related("sender", "reply_to__sender")
        .prefetch_related("media", "reactions__user")
        .annotate(
            read_by_count=Count(
                "statuses__recipient",
                filter=Q(statuses__is_read=True),
                distinct=True,
            )
        )
        .order_by("-created_at", "-id")
    )


def _mark_read_bulk(messages, user):
    ids = [m.id for m in messages if m.sender_id != user.id]
    if not ids:
        return
    MessageStatus.objects.filter(
        message_id__in=ids, recipient=user, is_read=False
    ).update(is_read=True, is_delivered=True, read_at=timezone.now())


""" User search across local DB and central ERP directory """


class UserSearchView(APIView):
    """Search users — local DB + central ERP directory merged."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return APIResponse.error(
                message="Query must be at least 2 characters.", status_code=400
            )

        from django.contrib.auth import get_user_model

        User = get_user_model()

        local = list(
            User.objects.filter(
                Q(name__icontains=query) | Q(employee_id__icontains=query)
            ).exclude(pk=request.user.pk)[:20]
        )
        local_central_ids = {u.central_id for u in local}

        results = [
            {
                "id": u.id,
                "central_id": u.central_id,
                "name": u.name,
                "position": u.position,
                "avatar_url": u.avatar_url,
                "is_active_on_social": True,
            }
            for u in local
        ]

        cache_key = f"central_search:{query}"
        central = cache.get(cache_key)
        if central is None:
            central = _search_central(query, request)
            cache.set(cache_key, central, 30)

        for emp in central:
            if emp["id"] not in local_central_ids:
                results.append(
                    {
                        "id": None,
                        "central_id": emp["id"],
                        "name": emp["name"],
                        "position": emp.get("job_title", ""),
                        "avatar_url": emp.get("avatar_url"),
                        "is_active_on_social": False,
                    }
                )

        return APIResponse.success(data=results)


def _search_central(query, request):
    import requests as req

    try:
        resp = req.get(
            "https://erp.betopiagroup.com/employee-directory/",
            params={"search": query},
            headers={"Authorization": f"Bearer {request.user.central_access_token}"},
            cookies={"session_id": request.COOKIES.get("session_id", "")},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data if isinstance(data, list) else data.get("employees", [])
    except Exception as e:
        logger.error("Central directory search failed | error=%s", e)
    return []


""" Conversation Views """


class ConversationListView(APIView):
    """GET - chat list. POST - start or retrieve a DM."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _conv_qs(request.user)
        return APIResponse.success(
            data=ConversationSerializer(
                qs, many=True, context={"request": request}
            ).data
        )

    def post(self, request):
        target_id = request.data.get("user_id")
        if not target_id:
            return APIResponse.error(message="user_id required.", status_code=400)

        from django.contrib.auth import get_user_model

        User = get_user_model()

        try:
            target = User.objects.get(pk=target_id)
        except User.DoesNotExist:
            return APIResponse.error(
                message="User not found or not yet active on social.", status_code=404
            )

        if target == request.user:
            return APIResponse.error(
                message="Cannot message yourself.", status_code=400
            )

        conv, created = _get_or_create_dm(request.user, target)
        data = ConversationSerializer(
            _conv_qs(request.user).get(pk=conv.pk), context={"request": request}
        ).data
        return APIResponse.success(data=data, status_code=201 if created else 200)


class ConversationParticipantsView(APIView):
    """GET - list all participants in a group conversation."""

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

        data = [
            {
                "id": p.user.id,
                "name": p.user.name,
                "avatar_url": p.user.avatar_url,
                "is_online": p.is_online,
                "last_seen": p.last_seen,
            }
            for p in participants
        ]
        return APIResponse.success(data=data)
