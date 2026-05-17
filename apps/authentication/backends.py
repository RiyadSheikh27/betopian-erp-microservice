import logging

import requests
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()
logger = logging.getLogger("apps.authentication")

CENTRAL_PROFILE_URL = "https://erp.betopiagroup.com/profiles/"
CENTRAL_TIMEOUT = 20


class CentralTokenAuthentication(BaseAuthentication):

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return None

        session_id = request.COOKIES.get("session_id", "")
        profile = self._fetch_profile(token, session_id)
        user = self._sync_user(profile, token)

        logger.debug(
            "Request authenticated | user_id=%s email=%s",
            user.pk,
            user.email,
        )
        return (user, token)

    def _fetch_profile(self, token, session_id):
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
            logger.warning("Central profile 403 — invalid session_id cookie")
            raise AuthenticationFailed("Session invalid. Please login again.")
        if resp.status_code == 500:
            logger.error("Central profile returned 500 — server error on central ERP")
            raise AuthenticationFailed(
                "Central auth service is temporarily unavailable. Try again."
            )

        if resp.status_code != 200:
            logger.error(
                "Central profile returned %s | body=%s",
                resp.status_code,
                resp.text,
            )
            raise AuthenticationFailed("Central auth service error.")

        return resp.json()

    def _sync_user(self, profile, token):
        """
        Create user on first hit — no prior login step needed.
        On subsequent requests, only write to DB if something actually changed.
        This prevents unnecessary DB writes on every request under high traffic.
        """
        employee_id = profile["employee_id"]

        # Map central profile fields to our model fields
        incoming = {
            "central_id": profile["id"],
            "email": profile["email"],
            "username": profile["email"].split("@")[0],
            "name": profile["name"],
            "phone": profile.get("phone", ""),
            "department": profile.get("department", ""),
            "position": profile.get("position", ""),
            "avatar_url": profile.get("avatar_base64", ""),
        }

        try:
            user = User.objects.get(employee_id=employee_id)

            # Check if anything changed — compare field by field
            changed = {
                field: value
                for field, value in incoming.items()
                if getattr(user, field) != value
            }

            # Always update token regardless — it changes on every login
            changed["central_access_token"] = token

            if len(changed) > 1:  # more than just token changed
                for field, value in changed.items():
                    setattr(user, field, value)
                user.save(update_fields=list(changed.keys()) + ["updated_at"])
                logger.info(
                    "User profile synced | user_id=%s changed_fields=%s",
                    user.pk,
                    list(changed.keys()),
                )
            else:
                # Only token changed — update just that, cheapest possible write
                User.objects.filter(pk=user.pk).update(central_access_token=token)

        except User.DoesNotExist:
            # First time this user hits any endpoint — create immediately
            user = User.objects.create(
                employee_id=employee_id,
                central_access_token=token,
                is_active=True,
                **incoming,
            )
            logger.info(
                "New user created on first request | user_id=%s email=%s",
                user.pk,
                user.email,
            )

        return user
