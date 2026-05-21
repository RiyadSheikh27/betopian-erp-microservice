import logging
import requests

from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()
logger = logging.getLogger("apps.authentication")

CENTRAL_PROFILE_URL = "https://erp.betopiagroup.com/profiles/"
CENTRAL_EMPLOYEE_URL = "https://erp.betopiagroup.com/employee-directory/"
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

        # logger.info("Profile Response: %s", profile)

        user = self._sync_user(profile, token)
        # Community auto-assignment.
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

        return resp.json()

    def _sync_user(self, profile, token):
        employee_id = profile["employee_id"]
    
        incoming = {
            "central_id": profile["id"],
            "email": profile["email"],
            "username": profile["email"].split("@")[0],
            "name": profile["name"],
            "phone": profile.get("phone", ""),
            "department": profile.get("department", ""),
            "position": profile.get("position", ""),
            "location": profile.get("address", ""),
            "company": profile.get("company", "") or profile.get("company_name", ""),
            "avatar_url": profile.get("avatar_url", ""),
        }
    
        try:
            user = User.objects.get(employee_id=employee_id)
            changed = {k: v for k, v in incoming.items() if getattr(user, k) != v}
            changed["central_access_token"] = token
    
            if changed:
                for k, v in changed.items():
                    setattr(user, k, v)
                user.save(update_fields=list(changed.keys()) + ["updated_at"])
                logger.info("User synced | user_id=%s fields=%s", user.pk, list(changed.keys()))
            else:
                User.objects.filter(pk=user.pk).update(central_access_token=token)
    
        except User.DoesNotExist:
            user, created = User.objects.update_or_create(
                central_id=incoming["central_id"],
                defaults={
                    "employee_id": employee_id,
                    "central_access_token": token,
                    "is_active": True,
                    **incoming,
                },
            )
            if created:
                logger.info("New user created | user_id=%s email=%s", user.pk, user.email)
            else:
                logger.info("User re-linked by central_id | user_id=%s email=%s", user.pk, user.email)
    
        try:
            from apps.contents.community import assign_communities
            assign_communities(user, profile)
        except Exception as e:
            logger.error("Community assignment failed | user_id=%s error=%s", user.pk, e)
    
        return user  # ← this was missing

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
            # Unwrap {"employee": {...}} — fall back to flat dict if already flat
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
