import json
import logging

from apps.utils.fcm import send_to_user
from apps.utils.apns_voip import send_voip_push

logger = logging.getLogger("apps.chat")


def _preview(msg_data):
    msg_type = msg_data.get("type", "text")
    body = (msg_data.get("body") or "").strip()
    if msg_data.get("story"):
        return body[:120] if body else "Replied to your story"
    if body:
        return body[:120]
    if msg_type == "media":
        return "Sent a photo"
    if msg_type == "doc":
        return "Sent a document"
    return "New message"


def _title(conv, sender_name):
    if conv.type == "dm":
        return sender_name
    if conv.community_id and conv.community:
        return conv.community.name
    return "Group chat"


def notify_chat_message(conv_id, sender, msg_data):
    from .models import Conversation, ConversationParticipant

    try:
        conv = Conversation.objects.select_related("community").get(pk=conv_id)
    except Conversation.DoesNotExist:
        return

    recipient_ids = (
        ConversationParticipant.objects.filter(conversation_id=conv_id)
        .exclude(user_id=sender.id)
        .values_list("user_id", flat=True)
    )

    preview = _preview(msg_data)
    title = _title(conv, sender.name)
    body = preview if conv.type == "dm" else f"{sender.name}: {preview}"

    payload = json.dumps(msg_data)
    conv_id_str = str(conv_id)
    for user_id in recipient_ids:
        send_to_user(
            user_id,
            title=title,
            body=body,
            data={
                "type": "chat_message",
                "conv_id": conv_id_str,
                "conversation_id": conv_id_str,
                "message_id": msg_data.get("id", ""),
                "payload": payload,
            },
        )


def notify_incoming_call(session, caller):
    """iOS: APNs VoIP for CallKit. Android (and iOS without VoIP token): FCM data."""
    from apps.notifications.models import DeviceToken

    call_type = session.call_type
    label = "Video call" if call_type == "video" else "Voice call"
    call_id = str(session.id)
    conv_id = str(session.conversation_id)
    fcm_tokens = []

    for device in DeviceToken.objects.filter(user_id=session.callee_id):
        if device.platform == DeviceToken.Platform.IOS and device.voip_token:
            result = send_voip_push(
                device.voip_token,
                {
                    "aps": {"content-available": 1},
                    "call_id": call_id,
                    "id": call_id,
                    "caller_name": caller.name,
                    "nameCaller": caller.name,
                    "caller_id": str(caller.id),
                    "conversation_id": conv_id,
                    "call_type": call_type,
                    "type": "incoming_call",
                },
            )
            if result == "dead":
                device.voip_token = None
                device.save(update_fields=["voip_token", "updated_at"])
            continue

        fcm_tokens.append(device.fcm_token)

    if fcm_tokens:
        send_to_user(
            session.callee_id,
            title=caller.name,
            body=f"Incoming {label.lower()}",
            high_priority=True,
            tokens=fcm_tokens,
            data={
                "type": "incoming_call",
                "call_id": call_id,
                "conv_id": conv_id,
                "conversation_id": conv_id,
                "caller_id": str(caller.id),
                "caller_name": caller.name,
                "caller_avatar": caller.avatar_url or "",
                "call_type": call_type,
            },
        )

    logger.info(
        "Incoming call push | call=%s caller=%s callee=%s",
        session.id,
        caller.id,
        session.callee_id,
    )
