import hashlib
import logging

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()
logger = logging.getLogger("apps.authentication")


class AppJWTAuthentication(BaseAuthentication):
    """Authenticate requests using our own issued JWT (from SSO login)."""

    def authenticate(self, request):
        from .utils import decode_jwt_payload, get_token_from_request

        token = get_token_from_request(request)
        if not token:
            return None

        payload = decode_jwt_payload(token)
        if not payload or not payload.get("email"):
            return None

        user = User.objects.filter(email__iexact=payload["email"]).first()
        if not user:
            return None
        return (user, token)


CENTRAL_PROFILE_URL = "https://erp.betopiagroup.com/profiles/"
CENTRAL_EMPLOYEE_URL = "https://erp.betopiagroup.com/employee-directory/"
CENTRAL_TIMEOUT = 20
PROFILE_CACHE_TTL = 300  # seconds — skip central ERP round-trip on repeat requests


class CentralTokenAuthentication(BaseAuthentication):

    @staticmethod
    def _profile_cache_key(token):
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return f"auth:profile:{token_hash}"

    @staticmethod
    def _user_cache_key(employee_id):
        return f"auth:user_pk:{employee_id}"

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
        return (user, token)

    def _fetch_profile(self, token, session_id):
        cache_key = self._profile_cache_key(token)
        cached = cache.get(cache_key)
        if cached is not None:
            logger.debug("Profile cache hit")
            return cached

        try:
            resp = requests.get(
                CENTRAL_PROFILE_URL,
                headers={"Authorization": f"Bearer {token}"},
                cookies={"session_id": session_id} if session_id else {},
                timeout=CENTRAL_TIMEOUT,
            )
        except requests.Timeout:
            raise AuthenticationFailed("Central auth service timed out. Try again.")
        except requests.RequestException as e:
            logger.error("Central profile API unreachable | error=%s", e)
            raise AuthenticationFailed("Central auth service unavailable.")

        if resp.status_code == 401:
            raise AuthenticationFailed("Invalid or expired token.")
        if resp.status_code == 403:
            raise AuthenticationFailed("Session invalid. Please login again.")
        if resp.status_code == 500:
            raise AuthenticationFailed(
                "Central auth service is temporarily unavailable."
            )
        if resp.status_code != 200:
            logger.error(
                "Central profile returned %s | body=%s", resp.status_code, resp.text
            )
            raise AuthenticationFailed("Central auth service error.")

        profile = resp.json()
        cache.set(cache_key, profile, PROFILE_CACHE_TTL)
        return profile

    def _sync_user(self, profile, token):
        from .utils import sync_user_from_profile

        employee_id = profile["employee_id"]
        user_cache_key = self._user_cache_key(employee_id)

        user, created, changed = sync_user_from_profile(profile, token=token)
        cache.set(user_cache_key, str(user.pk), PROFILE_CACHE_TTL)

        if created:
            logger.info("New user created | user_id=%s email=%s", user.pk, user.email)
        else:
            logger.info("User synced | user_id=%s email=%s", user.pk, user.email)

        try:
            from apps.contents.tasks import enqueue_community_assignment

            enqueue_community_assignment(
                user, profile, created=created, changed_fields=changed
            )
        except Exception as e:
            logger.error(
                "Community assignment failed | user_id=%s error=%s", user.pk, e
            )

        return user


def fetch_central_profile(central_id, token, session_id):
    """
    Fetch a single employee from central ERP by their ID.
    The employee-directory API returns: {"employee": {...}}
    Returns the flat employee dict, or None on failure.
    """
    url = f"{CENTRAL_EMPLOYEE_URL}{central_id}/"
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            cookies={"session_id": session_id} if session_id else {},
            timeout=CENTRAL_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Unwrap {"employee": {...}} - fall back to flat dict if already flat
            employee = data.get("employee") or data
            logger.debug(
                "Employee fetched | central_id=%s name=%s",
                central_id,
                employee.get("name", "?"),
            )
            return employee

        logger.warning(
            "Employee fetch failed | url=%s status=%s body=%s",
            url,
            resp.status_code,
            resp.text[:200],
        )
        return None

    except Exception as e:
        logger.error("Employee fetch error | central_id=%s error=%s", central_id, e)
        return None


def fetch_central_profiles_bulk(central_ids, token, session_id):
    """
    Fetch multiple employee profiles in parallel.
    Returns {central_id: employee_dict_or_None}
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not central_ids:
        return {}

    results = {}
    with ThreadPoolExecutor(max_workers=min(len(central_ids), 10)) as executor:
        futures = {
            executor.submit(fetch_central_profile, cid, token, session_id): cid
            for cid in central_ids
        }
        for future in as_completed(futures):
            cid = futures[future]
            try:
                results[cid] = future.result()
            except Exception as e:
                logger.error(
                    "Bulk profile fetch error | central_id=%s error=%s", cid, e
                )
                results[cid] = None

    logger.info(
        "Bulk employee fetch | requested=%d fetched=%d failed=%d",
        len(central_ids),
        sum(1 for v in results.values() if v),
        sum(1 for v in results.values() if not v),
    )
    return results
