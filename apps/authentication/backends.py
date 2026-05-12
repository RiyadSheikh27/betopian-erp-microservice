import logging

import requests
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()
logger = logging.getLogger("apps.authentication")

CENTRAL_LOGIN_URL = "https://erp.betopiagroup.com/login/"
CENTRAL_PROFILE_URL = "https://erp.betopiagroup.com/profiles/"
CENTRAL_TIMEOUT = 20

"""Custom authentication backend that validates tokens against the central ERP and mirrors user profiles locally."""

class CentralTokenAuthentication(BaseAuthentication):
    """Authenticates every request against the central ERP."""

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return None

        # session_id cookie must be forwarded from the original central login
        session_id = request.COOKIES.get("session_id", "")

        profile = self._fetch_profile(token, session_id)
        user = self._upsert_user(profile, token)

        logger.debug(
            "Request authenticated | user_id=%s email=%s",
            user.pk,
            user.email,
        )
        return (user, token)

    def _fetch_profile(self, token, session_id):
        """
        Verify token and fetch user profile from central ERP.
        Raises AuthenticationFailed on any failure.
        """
        try:
            resp = requests.get(
                CENTRAL_PROFILE_URL,
                headers={"Authorization": f"Bearer {token}"},
                cookies={"session_id": session_id} if session_id else {},
                timeout=CENTRAL_TIMEOUT,
            )
        except requests.Timeout:
            logger.error("Central profile API timed out")
            raise AuthenticationFailed("Central auth service timed out. Try again.")
        except requests.RequestException as e:
            logger.error("Central profile API unreachable | error=%s", str(e))
            raise AuthenticationFailed("Central auth service unavailable.")

        if resp.status_code == 401:
            raise AuthenticationFailed("Invalid or expired token.")
        if resp.status_code == 403:
            logger.warning(
                "Central profile returned 403 — missing or invalid session_id cookie"
            )
            raise AuthenticationFailed(
                "Session invalid. Please login again through the central ERP."
            )
        if resp.status_code != 200:
            logger.error(
                "Central profile API returned %s | body=%s", resp.status_code, resp.text
            )
            raise AuthenticationFailed("Central auth service error.")

        return resp.json()

    def _upsert_user(self, profile, token):
        """
        Create or update local user mirror from central profile.
        Called on every request so profile is always fresh.
        """
        username = profile["email"].split("@")[0]

        user, created = User.objects.update_or_create(
            employee_id=profile["employee_id"],
            defaults={
                "email": profile["email"],
                "username": username,
                "name": profile["name"],
                "phone": profile.get("phone", ""),
                "department": profile.get("department", ""),
                "position": profile.get("position", ""),
                "avatar_url": profile.get("avatar_url", ""),
                "central_access_token": token,
                "is_active": True,
            },
        )

        if created:
            logger.info(
                "New user mirrored from central | user_id=%s email=%s",
                user.pk,
                user.email,
            )

        return user
