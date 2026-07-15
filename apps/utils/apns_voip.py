import logging
import time

import httpx
import jwt
from django.conf import settings

logger = logging.getLogger("apps.utils.apns_voip")

_client = None
_jwt_cache = {"token": None, "exp": 0}


def _configured():
    return bool(settings.APNS_KEY_PATH and settings.APNS_KEY_ID and settings.APNS_TEAM_ID)


def _host():
    if settings.APNS_USE_SANDBOX:
        return "https://api.sandbox.push.apple.com"
    return "https://api.push.apple.com"


def _get_client():
    global _client
    if _client is None:
        _client = httpx.Client(http2=True, timeout=10.0)
    return _client


def _auth_token():
    now = int(time.time())
    if _jwt_cache["token"] and _jwt_cache["exp"] > now + 60:
        return _jwt_cache["token"]

    with open(settings.APNS_KEY_PATH, encoding="utf-8") as key_file:
        key = key_file.read()

    token = jwt.encode(
        {"iss": settings.APNS_TEAM_ID, "iat": now},
        key,
        algorithm="ES256",
        headers={"alg": "ES256", "kid": settings.APNS_KEY_ID},
    )
    _jwt_cache["token"] = token
    _jwt_cache["exp"] = now + 3300
    return token


def send_voip_push(device_token, payload):
    """
    Send a PushKit VoIP notification. Returns True on success, False on failure,
    or "dead" when Apple reports an invalid token.
    """
    if not _configured():
        logger.warning("APNS_KEY_PATH / APNS_KEY_ID / APNS_TEAM_ID not set — VoIP disabled")
        return False

    url = f"{_host()}/3/device/{device_token}"
    headers = {
        "authorization": f"bearer {_auth_token()}",
        "apns-push-type": "voip",
        "apns-topic": settings.APNS_TOPIC,
        "apns-priority": "10",
        "content-type": "application/json",
    }

    try:
        response = _get_client().post(url, headers=headers, json=payload)
    except Exception:
        logger.exception("APNs VoIP request failed")
        return False

    if response.status_code == 200:
        logger.info("APNs VoIP sent | token=%s…", device_token[:8])
        return True

    logger.warning(
        "APNs VoIP failed | status=%s body=%s",
        response.status_code,
        response.text,
    )
    if response.status_code in (400, 410):
        return "dead"
    return False
