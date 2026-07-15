import logging

from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.utils.throttles import AuthThrottle

from apps.utils.response import APIResponse
from .serializers import SSOLoginSerializer, UserProfileSerializer
from .utils import (
    SSOServiceError,
    decode_ms_claims,
    exchange_central_access_token,
    fetch_central_profile,
    sync_user_from_profile,
)

logger = logging.getLogger("apps.authentication")


class SSOLoginView(APIView):
    """Verify a Microsoft token via central ERP and issue our own JWT."""

    authentication_classes = []
    permission_classes = []
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = SSOLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                errors=serializer.errors,
                message="Invalid request payload.",
                status_code=422,
            )

        data = serializer.validated_data
        ms_token = data.get("access_token") or data.get("id_token")

        session_id = request.COOKIES.get("session_id", "")
        ms_claims = decode_ms_claims(ms_token)
        azure_oid = ms_claims.get("oid")
        profile = None
        created = False
        changed = set()

        try:
            central_access_token = exchange_central_access_token(
                ms_token=ms_token,
                app_version=data.get("appVersion", ""),
                device_id=data.get("deviceId", ""),
                session_id=session_id,
            )
            profile = fetch_central_profile(central_access_token, session_id=session_id)
        except SSOServiceError as exc:
            logger.warning("SSO login failed: %s", exc.message)
            return APIResponse.error(message=exc.message, status_code=exc.status_code)

        user, created, changed = sync_user_from_profile(profile, token=central_access_token)
        if created:
            logger.info("SSO user created | email=%s", user.email)
        else:
            logger.info("SSO user synced | email=%s", user.email)

        if not azure_oid:
            azure_oid = str(user.central_id)

        logger.info(
            "SSO login | email=%s app_version=%s device_id=%s",
            user.email,
            data.get("appVersion", ""),
            data.get("deviceId", ""),
        )

        if data.get("fcm_token"):
            from apps.notifications.views import extract_voip_token, register_device

            register_device(
                user,
                data["deviceId"],
                data["fcm_token"],
                data["platform"],
                voip_token=extract_voip_token(data),
            )
            logger.info("Device registered for push | user=%s device=%s", user.pk, data["deviceId"])

        from apps.contents.tasks import enqueue_community_assignment

        enqueue_community_assignment(
            user, profile, created=created, changed_fields=changed
        )

        access = AccessToken()
        access["uid"] = azure_oid
        access["email"] = user.email

        refresh = RefreshToken()
        refresh["uid"] = azure_oid
        refresh["email"] = user.email

        return APIResponse.success(
            data={
                "access_token": str(access),
                "refresh_token": str(refresh),
                "user": UserProfileSerializer(user).data,
            },
            message="SSO login successful.",
        )


class ProfileView(APIView):
    """
    Returns the authenticated user's profile.
    Read-only. Central ERP owns all user data.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return APIResponse.success(data=serializer.data)


class LogoutView(APIView):
    """We don't issue or store session tokens - central ERP does."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        logger.info(
            "User logged out | user_id=%s email=%s", request.user.pk, request.user.email
        )
        return APIResponse.success(message="Logged out successfully.")
