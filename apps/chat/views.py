import logging
import math
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q, Subquery, OuterRef
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from apps.utils.media import compress_image
from apps.utils.response import APIResponse
from apps.contents.views import _encode_cursor, _decode_cursor, _apply_cursor

import hmac
import hashlib
import time
from django.conf import settings as django_settings

from .models import (
    Conversation,
    ConversationParticipant,
    Message,
    MessageMedia,
    MessageReaction,
    MessageStatus,
    CallSession,
    CallLog,
)
from .push import notify_incoming_call
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


def _parse_page_size(request, default=PAGE_SIZE):
    try:
        return min(int(request.query_params.get("page_size", default)), 50)
    except (TypeError, ValueError):
        return default


def _parse_page(request, default=1):
    try:
        return max(1, int(request.query_params.get("page", default)))
    except (TypeError, ValueError):
        return default


def _apply_conv_cursor(queryset, cursor_str):
    """Filter to conversations older than cursor (by last_activity)."""
    decoded = _decode_cursor(cursor_str)
    if not decoded:
        return queryset, "Invalid or tampered cursor."
    activity_str, conv_id = decoded
    return (
        queryset.filter(
            Q(last_activity__lt=activity_str)
            | Q(last_activity=activity_str, id__lt=conv_id)
        ),
        None,
    )


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
        .select_related("sender", "reply_to__sender", "story__author")
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


def _fetch_central_employees(request, *, query=None, page=1, page_size=50):
    """Fetch employees from central ERP directory (search or paginated list)."""
    import requests as req

    from apps.authentication.utils import get_central_access_token

    token = get_central_access_token(request)
    session_id = request.COOKIES.get("session_id", "")
    params = {"page": page, "limit": page_size}
    if query:
        params["search"] = query
    try:
        resp = req.get(
            "https://erp.betopiagroup.com/employee-directory/",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            cookies={"session_id": session_id} if session_id else {},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "employees": data.get("employees", []),
                "total": data.get("total", 0),
                "limit": data.get("limit", page_size) or page_size,
            }
        logger.warning("Central employee fetch failed | status=%s", resp.status_code)
    except Exception as e:
        logger.error("Central employee fetch error | %s", e)
    return {"employees": [], "total": 0, "limit": page_size}

def _pagination_meta(payload, page, page_size):
    total = payload.get("total", 0)
    limit = payload.get("limit", page_size) or page_size
    total_pages = max(1, math.ceil(total / limit)) if total else 1
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_more": page < total_pages,
    }


def _map_employee_results(employees, request_user):
    """Enrich central ERP employees with local user data; skip self."""
    User = get_user_model()
    self_code = str(request_user.employee_id).strip()
    results = []
    for emp in employees:
        emp_code = str(emp.get("employee_code", "")).strip()
        if emp_code == self_code:
            continue
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
    return results


""" Views Section """

class UserSearchView(APIView):
    """
    Search or list employees from central ERP directory.
    Supports pagination via page and page_size for both list and search modes.
    Matches employee_code with local employee_id to flag social status.
    Results cached 30s to avoid hammering central ERP.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        page = _parse_page(request)
        page_size = _parse_page_size(request)

        cache_key = f"central_employees:{query}:{page}:{page_size}"
        payload = cache.get(cache_key)
        if payload is None:
            payload = _fetch_central_employees(
                request, query=query or None, page=page, page_size=page_size
            )
            cache.set(cache_key, payload, 30)

        return APIResponse.success(
            data=_map_employee_results(payload["employees"], request.user),
            meta=_pagination_meta(payload, page, page_size),
        )


class ConversationListView(APIView):
    """
    GET - cursor-paginated chat list ordered by last activity (newest first).
    POST - start or retrieve a DM. Body: { user_id }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        page_size = _parse_page_size(request)
        qs = _conv_qs(request.user)
        cursor = request.query_params.get("cursor")
        if cursor:
            qs, err = _apply_conv_cursor(qs, cursor)
            if err:
                return APIResponse.error(errors={"cursor": err}, status_code=400)

        items = list(qs[: page_size + 1])
        has_more = len(items) > page_size
        if has_more:
            items = items[:page_size]

        return APIResponse.success(
            data=ConversationSerializer(
                items, many=True, context={"request": request}
            ).data,
            meta={
                "next_cursor": (
                    _encode_cursor(items[-1].last_activity, items[-1].id)
                    if has_more
                    else None
                ),
                "has_more": has_more,
                "page_size": page_size,
            },
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
    GET  - cursor-paginated message history, newest first.
         Pass ?cursor= to load older messages (scroll up, WhatsApp-style).
         Auto-marks read on the latest page only.
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

        page_size = _parse_page_size(request)
        qs = _msg_qs(conv)
        cursor = request.query_params.get("cursor")
        if cursor:
            qs, err = _apply_cursor(qs, cursor)
            if err:
                return APIResponse.error(errors={"cursor": err}, status_code=400)

        items = list(qs[: page_size + 1])
        has_more = len(items) > page_size
        if has_more:
            items = items[:page_size]

        if not cursor:
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
                "page_size": page_size,
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
                "story_id": request.data.get("story_id"),
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

        story = None
        story_id = vd.get("story_id")
        if story_id:
            from apps.story.models import Story
            from apps.story.serializers import get_active_story

            try:
                story = get_active_story(story_id)
            except Story.DoesNotExist:
                return APIResponse.error(
                    errors={"story_id": "Story not found or expired."},
                    status_code=400,
                )

        msg = Message.objects.create(
            conversation=conv,
            sender=request.user,
            type=msg_type,
            body=vd["body"],
            reply_to_id=vd.get("reply_to_id"),
            story=story,
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


""" 1:1 Calls (REST lifecycle + push) """

User = get_user_model()

_CALL_LOG_STATUS = {
    CallSession.Status.ENDED: CallLog.CallStatus.COMPLETED,
    CallSession.Status.MISSED: CallLog.CallStatus.MISSED,
    CallSession.Status.DECLINED: CallLog.CallStatus.DECLINED,
    CallSession.Status.CANCELLED: CallLog.CallStatus.CANCELLED,
}


def _format_call_duration(seconds):
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def _serialize_call(session):
    return {
        "id": str(session.id),
        "conv_id": str(session.conversation_id),
        "caller_id": str(session.caller_id),
        "callee_id": str(session.callee_id),
        "call_type": session.call_type,
        "status": session.status,
        "duration": session.duration,
        "created_at": session.created_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
    }


def _call_channel(call_id):
    return f"call_{call_id}"


def _broadcast_call(call_id, payload):
    layer = get_channel_layer()
    if not layer:
        return
    async_to_sync(layer.group_send)(
        _call_channel(call_id),
        {"type": "call_state", "payload": payload},
    )


def _signal_user(user_id, payload):
    layer = get_channel_layer()
    if not layer:
        return
    async_to_sync(layer.group_send)(
        f"notify_{user_id}",
        {"type": "call_signal", "envelope": payload},
    )


def _expire_stale_ringing():
    """Auto-miss calls that ring too long (no Celery required)."""
    cutoff = timezone.now() - timedelta(
        seconds=django_settings.CALL_RING_TIMEOUT_SECONDS
    )
    stale = CallSession.objects.filter(
        status=CallSession.Status.RINGING, created_at__lt=cutoff
    ).select_related("caller", "callee", "conversation")
    for session in stale:
        finalize_call(session, CallSession.Status.MISSED)


def _user_busy(user):
    return CallSession.objects.filter(
        Q(caller=user) | Q(callee=user),
        status__in=CallSession.ACTIVE_STATUSES,
    ).exists()


def _get_call_for_user(call_id, user, for_update=False):
    qs = CallSession.objects.select_related("caller", "callee", "conversation")
    if for_update:
        qs = qs.select_for_update()
    try:
        session = qs.get(pk=call_id)
    except CallSession.DoesNotExist:
        return None
    if user.id not in (session.caller_id, session.callee_id):
        return None
    return session


def finalize_call(session, new_status, duration=0):
    """
    Move call to a terminal state once. Creates chat CallLog + call message.
    Returns the updated session, or None if transition is invalid.
    """
    if new_status not in CallSession.TERMINAL_STATUSES:
        return None

    with transaction.atomic():
        session = (
            CallSession.objects.select_for_update()
            .select_related("caller", "callee", "conversation")
            .filter(pk=session.pk)
            .first()
        )
        if not session or session.status in CallSession.TERMINAL_STATUSES:
            return session
        if session.status not in CallSession.ACTIVE_STATUSES:
            return None

        session.status = new_status
        session.duration = max(int(duration or 0), 0)
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "duration", "ended_at", "updated_at"])

        if session.call_log_id:
            return session

        log_status = _CALL_LOG_STATUS[new_status]
        call_type = session.call_type
        labels = {
            CallLog.CallStatus.COMPLETED: (
                f"{'📹' if call_type == 'video' else '📞'} {call_type.capitalize()} call"
                f" • {_format_call_duration(session.duration)}"
            ),
            CallLog.CallStatus.MISSED: (
                f"{'📹' if call_type == 'video' else '📞'} Missed {call_type} call"
            ),
            CallLog.CallStatus.DECLINED: (
                f"{'📹' if call_type == 'video' else '📞'} {call_type.capitalize()} call declined"
            ),
            CallLog.CallStatus.CANCELLED: (
                f"{'📹' if call_type == 'video' else '📞'} Cancelled {call_type} call"
            ),
        }
        body = labels.get(log_status, "Call")
        sender = session.caller if log_status != CallLog.CallStatus.DECLINED else session.callee

        msg = Message.objects.create(
            conversation=session.conversation,
            sender=sender,
            type=Message.Type.CALL,
            body=body,
        )
        log = CallLog.objects.create(
            conversation=session.conversation,
            caller=session.caller,
            receiver=session.callee,
            call_type=call_type,
            status=log_status,
            duration=session.duration,
            message=msg,
        )
        session.call_log = log
        session.save(update_fields=["call_log", "updated_at"])

        Conversation.objects.filter(pk=session.conversation_id).update(
            last_message=msg, last_activity=timezone.now()
        )

    payload = {"type": "call_ended", "call": _serialize_call(session)}
    _broadcast_call(session.id, payload)
    _signal_user(session.caller_id, payload)
    _signal_user(session.callee_id, payload)
    return session


class CallInitiateView(APIView):
    """Start a 1:1 call from anywhere - not tied to an open chat WebSocket."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        _expire_stale_ringing()

        callee_id = request.data.get("callee_id")
        call_type = (request.data.get("call_type") or "audio").lower()
        if call_type not in ("audio", "video"):
            return APIResponse.error(
                errors={"call_type": "Use audio or video."}, status_code=400
            )
        if not callee_id:
            return APIResponse.error(
                errors={"callee_id": "Required."}, status_code=400
            )
        if str(callee_id) == str(request.user.id):
            return APIResponse.error(message="Cannot call yourself.", status_code=400)

        try:
            callee = User.objects.get(pk=callee_id, is_active=True)
        except User.DoesNotExist:
            return APIResponse.error(message="User not found.", status_code=404)

        if _user_busy(request.user) or _user_busy(callee):
            return APIResponse.error(message="User is busy on another call.", status_code=409)

        conv, _ = _get_or_create_dm(request.user, callee)
        session = CallSession.objects.create(
            conversation=conv,
            caller=request.user,
            callee=callee,
            call_type=call_type,
            status=CallSession.Status.RINGING,
        )

        notify_incoming_call(session, request.user)
        ring_payload = {
            "type": "incoming_call",
            "call": _serialize_call(session),
            "caller": {
                "id": str(request.user.id),
                "name": request.user.name,
                "avatar_url": request.user.avatar_url or "",
            },
        }
        _signal_user(callee.id, ring_payload)

        logger.info(
            "Call initiated | call=%s caller=%s callee=%s type=%s",
            session.id,
            request.user.id,
            callee.id,
            call_type,
        )
        return APIResponse.success(
            data={
                "call": _serialize_call(session),
                "caller": {
                    "id": str(request.user.id),
                    "name": request.user.name,
                    "avatar_url": request.user.avatar_url or "",
                },
                "callee": {
                    "id": str(callee.id),
                    "name": callee.name,
                    "avatar_url": callee.avatar_url or "",
                },
            },
            message="Call ringing.",
            status_code=201,
        )


class CallDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, call_id):
        _expire_stale_ringing()
        session = _get_call_for_user(call_id, request.user)
        if not session:
            return APIResponse.error(message="Call not found.", status_code=404)
        return APIResponse.success(data={"call": _serialize_call(session)})


class CallAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, call_id):
        with transaction.atomic():
            session = _get_call_for_user(call_id, request.user, for_update=True)
            if not session:
                return APIResponse.error(message="Call not found.", status_code=404)
            if session.callee_id != request.user.id:
                return APIResponse.error(message="Only the callee can accept.", status_code=403)
            if session.status != CallSession.Status.RINGING:
                return APIResponse.error(
                    message=f"Call is already {session.status}.", status_code=409
                )
            session.status = CallSession.Status.ACCEPTED
            session.save(update_fields=["status", "updated_at"])

        payload = {
            "type": "call_accepted",
            "call": _serialize_call(session),
            "accepted_by": str(request.user.id),
        }
        _broadcast_call(session.id, payload)
        _signal_user(session.caller_id, payload)
        _signal_user(session.callee_id, payload)
        logger.info("Call accepted | call=%s callee=%s", call_id, request.user.id)
        return APIResponse.success(data={"call": _serialize_call(session)})


class CallDeclineView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, call_id):
        session = _get_call_for_user(call_id, request.user)
        if not session:
            return APIResponse.error(message="Call not found.", status_code=404)
        if session.callee_id != request.user.id:
            return APIResponse.error(message="Only the callee can decline.", status_code=403)
        if session.status != CallSession.Status.RINGING:
            return APIResponse.error(
                message=f"Call is already {session.status}.", status_code=409
            )
        session = finalize_call(session, CallSession.Status.DECLINED)
        logger.info("Call declined | call=%s", call_id)
        return APIResponse.success(data={"call": _serialize_call(session)})


class CallCancelView(APIView):
    """Caller cancels while ringing → missed for the callee."""

    permission_classes = [IsAuthenticated]

    def post(self, request, call_id):
        session = _get_call_for_user(call_id, request.user)
        if not session:
            return APIResponse.error(message="Call not found.", status_code=404)
        if session.caller_id != request.user.id:
            return APIResponse.error(message="Only the caller can cancel.", status_code=403)
        if session.status != CallSession.Status.RINGING:
            return APIResponse.error(
                message=f"Call is already {session.status}.", status_code=409
            )
        session = finalize_call(session, CallSession.Status.MISSED)
        logger.info("Call cancelled/missed | call=%s", call_id)
        return APIResponse.success(data={"call": _serialize_call(session)})


class CallConnectedView(APIView):
    """Optional — client reports WebRTC media connected (for analytics / UI)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, call_id):
        session = _get_call_for_user(call_id, request.user)
        if not session:
            return APIResponse.error(message="Call not found.", status_code=404)
        if session.status not in (
            CallSession.Status.ACCEPTED,
            CallSession.Status.CONNECTED,
        ):
            return APIResponse.error(
                message=f"Call is {session.status}, not ready.", status_code=409
            )
        if session.status != CallSession.Status.CONNECTED:
            session.status = CallSession.Status.CONNECTED
            session.save(update_fields=["status", "updated_at"])
            payload = {"type": "call_connected", "call": _serialize_call(session)}
            _broadcast_call(session.id, payload)
        return APIResponse.success(data={"call": _serialize_call(session)})


class CallEndView(APIView):
    """End an active call — single entry point (prevents duplicate call logs)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, call_id):
        duration = request.data.get("duration", 0)
        try:
            duration = max(int(duration), 0)
        except (TypeError, ValueError):
            duration = 0

        session = _get_call_for_user(call_id, request.user)
        if not session:
            return APIResponse.error(message="Call not found.", status_code=404)
        if session.status in CallSession.TERMINAL_STATUSES:
            return APIResponse.success(data={"call": _serialize_call(session)})
        if session.status not in CallSession.ACTIVE_STATUSES:
            return APIResponse.error(
                message=f"Call is {session.status}.", status_code=409
            )

        session = finalize_call(session, CallSession.Status.ENDED, duration=duration)
        logger.info("Call ended | call=%s duration=%s", call_id, duration)
        return APIResponse.success(data={"call": _serialize_call(session)})


class TurnCredentialsView(APIView):
    """
    Returns temporary TURN credentials for WebRTC.
    Uses time-limited HMAC credentials (CoTURN REST API auth).
    Client fetches this before initiating a call.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        ttl = 24 * 3600  # 24 hours
        timestamp = int(time.time()) + ttl
        username = f"{timestamp}:{request.user.id}"
        secret = django_settings.TURN_SECRET
        password = base64_hmac(username, secret)

        return APIResponse.success(
            data={
                "ice_servers": [
                    {
                        "urls": [
                            f"stun:{django_settings.TURN_HOST}:3478",
                        ]
                    },
                    {
                        "urls": [
                            f"turn:{django_settings.TURN_HOST}:3478?transport=udp",
                            f"turn:{django_settings.TURN_HOST}:3478?transport=tcp",
                            f"turns:{django_settings.TURN_HOST}:5349?transport=tcp",
                        ],
                        "username": username,
                        "credential": password,
                    },
                ]
            }
        )


def base64_hmac(username, secret):
    import base64

    key = secret.encode()
    msg = username.encode()
    return base64.b64encode(hmac.new(key, msg, hashlib.sha1).digest()).decode()
