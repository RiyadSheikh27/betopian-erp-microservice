import json
import logging

from apps.utils.fcm import send_to_user

logger = logging.getLogger("apps.notifications")


def push_notification_event(recipient_id, event, data):
    """FCM push for in-app notification events (background / app closed)."""
    if event != "new":
        return

    actor = data.get("actor") or {}
    title = actor.get("name") or "Betopian"
    body = (data.get("message") or "You have a new notification")[:120]

    send_to_user(
        recipient_id,
        title=title,
        body=body,
        data={
            "type": "notification_event",
            "event": event,
            "notification_id": str(data.get("id", "")),
            "payload": json.dumps(data),
        },
    )
