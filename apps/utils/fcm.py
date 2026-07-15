import logging

from django.conf import settings

logger = logging.getLogger("apps.utils.fcm")

_app = None
ANDROID_ALERT_CHANNEL = "betopia_social_alerts_v2"


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


def send_to_user(user_id, *, title, body, data, high_priority=False, tokens=None):
    if not _get_app():
        return

    from firebase_admin import messaging
    from apps.notifications.models import DeviceToken

    if tokens is None:
        tokens = list(
            DeviceToken.objects.filter(user_id=user_id).values_list(
                "fcm_token", flat=True
            )
        )
    else:
        tokens = list(tokens)

    if not tokens:
        logger.debug("FCM skip | user=%s no tokens", user_id)
        return

    notification = None
    if title or body:
        notification = messaging.Notification(title=title or "Betopian", body=body or "")

    android_notification = None
    if notification:
        android_notification = messaging.AndroidNotification(
            channel_id=ANDROID_ALERT_CHANNEL,
        )

    android = messaging.AndroidConfig(
        priority="high" if high_priority else "normal",
        notification=android_notification,
    )

    apns_headers = {"apns-priority": "10" if high_priority else "5"}
    apns_payload = None
    if notification:
        apns_payload = messaging.APNSPayload(
            aps=messaging.Aps(sound="default"),
        )
    apns = messaging.APNSConfig(headers=apns_headers, payload=apns_payload)

    message = messaging.MulticastMessage(
        notification=notification,
        data={k: str(v) for k, v in data.items()},
        tokens=tokens,
        android=android,
        apns=apns,
    )
    response = messaging.send_each_for_multicast(message)
    logger.info(
        "FCM sent | user=%s success=%s failure=%s",
        user_id,
        response.success_count,
        response.failure_count,
    )

    if response.failure_count:
        dead = []
        for idx, resp in enumerate(response.responses):
            if not resp.success and resp.exception:
                dead.append(tokens[idx])
        if dead:
            DeviceToken.objects.filter(fcm_token__in=dead).delete()
