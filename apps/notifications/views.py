import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.utils.response import APIResponse
from .models import Notification
from .notify import get_unread_count, mark_all_seen, push_unread_count

logger = logging.getLogger("apps.notifications")

_UNSET = object()
_VOIP_KEYS = ("voip_token", "voip_push_token", "apns_voip_token")


def extract_voip_token(data):
    """First non-empty VoIP alias, or '' if aliases sent but empty; None if omitted."""
    if not any(k in data for k in _VOIP_KEYS):
        return None
    for key in _VOIP_KEYS:
        val = (data.get(key) or "").strip()
        if val:
            return val
    return ""


def register_device(user, device_id, fcm_token, platform, voip_token=_UNSET):
    """Upsert device tokens for this user + device_id."""
    from .models import DeviceToken

    DeviceToken.objects.filter(fcm_token=fcm_token).exclude(
        user=user, device_id=device_id
    ).delete()

    defaults = {"fcm_token": fcm_token, "platform": platform}
    if voip_token is not _UNSET:
        defaults["voip_token"] = voip_token or None

    DeviceToken.objects.update_or_create(
        user=user,
        device_id=device_id,
        defaults=defaults,
    )


def _serialize(items):
    rows = []
    for n in items:
        payload = {**n.payload, "is_read": n.is_read}
        rows.append(payload)
    return rows


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            page_size = min(int(request.query_params.get("page_size", 20)), 50)
            page = max(int(request.query_params.get("page", 1)), 1)
        except (TypeError, ValueError):
            page_size, page = 20, 1

        qs = Notification.objects.filter(recipient=request.user)
        total = qs.count()
        offset = (page - 1) * page_size
        items = list(qs[offset : offset + page_size])

        return APIResponse.success(
            data=_serialize(items),
            meta={
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": -(-total // page_size) if total else 0,
                "unread_count": get_unread_count(request.user),
            },
        )


class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return APIResponse.success(data={"unread_count": get_unread_count(request.user)})


class NotificationReadAllView(APIView):
    """
    Clears the badge (user opened the notification list).
    Individual notifications stay is_read=False until opened via /{id}/read/.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        mark_all_seen(request.user)
        push_unread_count(request.user.pk, 0)
        logger.debug("Notifications seen | user=%s", request.user.pk)
        return APIResponse.success(
            data={"unread_count": 0},
            message="Notifications marked as seen.",
        )


class NotificationReadView(APIView):
    """Mark a single notification as read when the user opens it."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, recipient=request.user)
        except Notification.DoesNotExist:
            return APIResponse.error(message="Notification not found.", status_code=404)

        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read", "updated_at"])

        return APIResponse.success(
            data={
                "id": str(notification.id),
                "is_read": True,
                "unread_count": get_unread_count(request.user),
            },
            message="Notification marked as read.",
        )


class NotificationDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, recipient=request.user)
        except Notification.DoesNotExist:
            return APIResponse.error(message="Notification not found.", status_code=404)

        notification.delete()
        logger.debug("Notification deleted | user=%s id=%s", request.user.pk, pk)
        return APIResponse.success(
            data={"unread_count": get_unread_count(request.user)},
            message="Notification deleted.",
        )


class DeviceRegisterView(APIView):
    """Register or update FCM token (e.g. after login or token refresh)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        device_id = (
            request.data.get("device_id") or request.data.get("deviceId") or ""
        ).strip()
        fcm_token = request.data.get("fcm_token", "").strip()
        platform = request.data.get("platform", "").lower()

        if not device_id or not fcm_token:
            return APIResponse.error(
                errors={"detail": "device_id (or deviceId) and fcm_token are required."},
                status_code=400,
            )
        if platform not in ("android", "ios"):
            return APIResponse.error(
                errors={"platform": "Use android or ios."},
                status_code=400,
            )

        from .models import DeviceToken

        existed = DeviceToken.objects.filter(
            user=request.user, device_id=device_id
        ).exists()
        register_device(
            request.user,
            device_id,
            fcm_token,
            platform,
            voip_token=extract_voip_token(request.data),
        )

        return APIResponse.success(
            message="Device registered." if not existed else "Device updated."
        )


class DeviceUnregisterView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        device_id = (
            request.data.get("device_id") or request.data.get("deviceId") or ""
        ).strip()
        if not device_id:
            return APIResponse.error(
                errors={"device_id": "Required (device_id or deviceId)."},
                status_code=400,
            )

        from .models import DeviceToken

        DeviceToken.objects.filter(
            user=request.user, device_id=device_id
        ).delete()
        return APIResponse.success(message="Device unregistered.")