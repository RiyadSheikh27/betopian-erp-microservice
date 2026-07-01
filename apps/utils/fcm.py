import json
import logging

from django.conf import settings

logger = logging.getLogger("apps.utils.fcm")

_app = None


def _get_app():
    global _app
    if _app is not None:
        return _app
    path = settings.FIREBASE_CREDENTIALS_PATH
    if not path:
        logger.warning("FIREBASE_CREDENTIALS_PATH not set — FCM disabled")
        return None
    import firebase_admin
    from firebase_admin import credentials

    cred = credentials.Certificate(path)
    _app = firebase_admin.initialize_app(cred)
    return _app


def send_to_user(user_id, *, title, body, data):
    if not _get_app():
        return

    from firebase_admin import messaging
    from apps.notifications.models import DeviceToken

    tokens = list(
        DeviceToken.objects.filter(user_id=user_id).values_list("fcm_token", flat=True)
    )
    if not tokens:
        logger.debug("FCM skip | user=%s no tokens", user_id)
        return

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in data.items()},
        tokens=tokens,
    )
    response = messaging.send_each_for_multicast(message)
    logger.info(
        "FCM sent | user=%s success=%s failure=%s",
        user_id,
        response.success_count,
        response.failure_count,
    )

    # Remove dead tokens
    if response.failure_count:
        dead = []
        for idx, resp in enumerate(response.responses):
            if not resp.success and resp.exception:
                dead.append(tokens[idx])
        if dead:
            DeviceToken.objects.filter(fcm_token__in=dead).delete()