import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

logger = logging.getLogger("apps.notifications")


def _owner(target_type, target):
    if target_type == "media":
        return target.post.author
    return target.author


def _content_label(target_type):
    if target_type == "reel":
        return "reel"
    if target_type == "story":
        return "story"
    return "post"


def _message(actor_name, others_count, target_type):
    label = _content_label(target_type)
    if others_count == 0:
        return f"{actor_name} reacted to your {label}."
    if others_count == 1:
        return f"{actor_name} and 1 other person reacted to your {label}."
    return f"{actor_name} and {others_count} other people reacted to your {label}."


def get_unread_count(user):
    """Badge count — notifications newer than last_seen_at."""
    from .models import Notification, NotificationState

    state, _ = NotificationState.objects.get_or_create(user=user)
    qs = Notification.objects.filter(recipient=user)
    if state.last_seen_at:
        qs = qs.filter(created_at__gt=state.last_seen_at)
    return qs.count()


def mark_all_seen(user):
    """Clear badge only — does not mark individual notifications as read."""
    from .models import NotificationState

    state, _ = NotificationState.objects.get_or_create(user=user)
    state.last_seen_at = timezone.now()
    state.save(update_fields=["last_seen_at", "updated_at"])


def deliver(recipient_id, event, data):
    """
    Single delivery entry point for real-time alerts.
    WebSocket + FCM push (same payload as WS envelope data).
    """
    channel_layer = get_channel_layer()
    if channel_layer:
        envelope = {"type": "notification_event", "event": event, "data": data}
        async_to_sync(channel_layer.group_send)(
            f"notify_{recipient_id}",
            {"type": "notification_event", "envelope": envelope},
        )
        logger.debug("Notification deliver | user=%s event=%s", recipient_id, event)

    from .push import push_notification_event

    push_notification_event(recipient_id, event, data)


def push_unread_count(recipient_id, count=None):
    if count is None:
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.get(pk=recipient_id)
        count = get_unread_count(user)
    deliver(recipient_id, "unread_count", {"unread_count": count})


def notify_reaction(actor, reaction, target_type, target, total_count):
    from .models import Notification

    owner = _owner(target_type, target)
    if owner.pk == actor.pk:
        return

    others_count = max(total_count - 1, 0)
    post_id = reel_id = story_id = None
    if target_type == "post":
        post_id = target.pk
    elif target_type == "media":
        post_id = target.post_id
    elif target_type == "reel":
        reel_id = target.pk
    elif target_type == "story":
        story_id = target.pk

    payload = {
        "event": "reaction",
        "message": _message(actor.name, others_count, target_type),
        "actor": {
            "id": str(actor.id),
            "name": actor.name,
            "avatar_url": actor.avatar_url or "",
        },
        "reaction": reaction,
        "others_count": others_count,
        "target_type": target_type,
        "target_id": str(target.pk),
        "post_id": str(post_id) if post_id else None,
        "reel_id": str(reel_id) if reel_id else None,
        "story_id": str(story_id) if story_id else None,
    }

    notification = Notification.objects.create(
        recipient=owner,
        event="reaction",
        payload=payload,
    )
    payload["id"] = str(notification.id)
    payload["is_read"] = False
    payload["created_at"] = notification.created_at.isoformat()
    notification.payload = payload
    notification.save(update_fields=["payload"])

    payload["unread_count"] = get_unread_count(owner)
    deliver(owner.pk, "new", payload)
    logger.debug(
        "Reaction notification | owner=%s actor=%s target=%s",
        owner.pk,
        actor.pk,
        target_type,
    )


def notify_comment(actor, comment, target_type, target):
    from .models import Notification

    if comment.parent_id:
        from apps.interactions.models import Comment

        parent = Comment.objects.select_related("user").get(pk=comment.parent_id)
        recipient = parent.user
        message = f"{actor.name} replied to your comment."
    else:
        recipient = _owner(target_type, target)
        message = f"{actor.name} commented on your {_content_label(target_type)}."

    if recipient.pk == actor.pk:
        return

    post_id = reel_id = None
    if target_type == "post":
        post_id = target.pk
    elif target_type == "media":
        post_id = target.post_id
    elif target_type == "reel":
        reel_id = target.pk

    preview = (comment.body or "").strip()[:120]

    payload = {
        "event": "comment",
        "message": message,
        "actor": {
            "id": str(actor.id),
            "name": actor.name,
            "avatar_url": actor.avatar_url or "",
        },
        "comment_id": str(comment.id),
        "comment_body": preview,
        "parent_id": str(comment.parent_id) if comment.parent_id else None,
        "target_type": target_type,
        "target_id": str(target.pk),
        "post_id": str(post_id) if post_id else None,
        "reel_id": str(reel_id) if reel_id else None,
    }

    notification = Notification.objects.create(
        recipient=recipient,
        event="comment",
        payload=payload,
    )
    payload["id"] = str(notification.id)
    payload["is_read"] = False
    payload["created_at"] = notification.created_at.isoformat()
    notification.payload = payload
    notification.save(update_fields=["payload"])

    payload["unread_count"] = get_unread_count(recipient)
    deliver(recipient.pk, "new", payload)
    logger.debug(
        "Comment notification | recipient=%s actor=%s target=%s",
        recipient.pk,
        actor.pk,
        target_type,
    )
