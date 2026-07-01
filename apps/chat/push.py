import json
import logging

from apps.utils.fcm import send_to_user

logger = logging.getLogger("apps.chat")


def _preview(msg_data):
    msg_type = msg_data.get("type", "text")
    body = (msg_data.get("body") or "").strip()
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
    for user_id in recipient_ids:
        send_to_user(
            user_id,
            title=title,
            body=body,
            data={
                "type": "chat_message",
                "conv_id": str(conv_id),
                "message_id": msg_data.get("id", ""),
                "payload": payload,
            },
        )
