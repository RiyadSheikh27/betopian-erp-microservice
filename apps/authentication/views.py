import logging

from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.utils.throttles import AuthThrottle

from apps.utils.response import APIResponse
from .models import User
from .serializers import SSOLoginSerializer, UserProfileSerializer
from .utils import (
    SSOServiceError,
    decode_ms_claims,
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

        ms_claims = decode_ms_claims(ms_token)
        azure_oid = ms_claims.get("oid")
        profile = None
        created = False
        changed = set()

        try:
            profile = fetch_central_profile(ms_token)
        except SSOServiceError as exc:
            # Invalid token always fails; a service outage lets a known user through.
            fallback_email = ms_claims.get("preferred_username") or ms_claims.get("upn")
            user = (
                None
                if exc.status_code == 401
                else User.objects.filter(email__iexact=fallback_email).first()
                if fallback_email
                else None
            )
            if user is None:
                logger.warning("SSO login failed: %s", exc.message)
                return APIResponse.error(
                    message=exc.message, status_code=exc.status_code
                )
            logger.warning(
                "Central profile unavailable, using stored data | email=%s", user.email
            )
        else:
            user, created, changed = sync_user_from_profile(profile, token=ms_token)
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
            from apps.notifications.views import register_device

            register_device(
                user,
                data["deviceId"],
                data["fcm_token"],
                data["platform"],
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
