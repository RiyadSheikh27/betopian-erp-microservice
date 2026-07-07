import jwt
import requests
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

CENTRAL_LOGIN_SSO_URL = "https://erp.betopiagroup.com/login-sso"
CENTRAL_PROFILE_URL = "https://erp.betopiagroup.com/profiles/"
CENTRAL_TIMEOUT = 15

User = get_user_model()


class SSOServiceError(Exception):
    def __init__(self, message, status_code=401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def decode_ms_claims(token):
    """
    Unverified decode of the Microsoft token, only to read oid/email for our own
    JWT. Authenticity is verified by the central system, not here.
    """
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except jwt.InvalidTokenError:
        return {}


def exchange_central_access_token(ms_token, app_version="", device_id="", session_id=""):
    """
    Exchange Microsoft token for central ERP access token via /login-sso.
    """
    payload = {
        "access_token": ms_token,
        "appVersion": app_version,
        "deviceId": device_id,
    }
    try:
        resp = requests.post(
            CENTRAL_LOGIN_SSO_URL,
            json=payload,
            cookies={"session_id": session_id} if session_id else {},
            timeout=CENTRAL_TIMEOUT,
        )
    except requests.RequestException:
        raise SSOServiceError("Central login service unreachable.", 503)

    if resp.status_code == 401:
        raise SSOServiceError("Invalid or expired Microsoft token.", 401)
    if resp.status_code != 200:
        raise SSOServiceError("Unable to login to central service.", 502)

    data = resp.json()
    central_access_token = data.get("access_token")
    if not central_access_token:
        raise SSOServiceError("Central login did not return access token.", 502)
    return central_access_token


def fetch_central_profile(access_token, session_id=""):
    """
    Fetch the user's profile from central ERP using the provided bearer token.
    Central validates the token: 200 = valid, 401 = invalid/expired.
    """
    try:
        resp = requests.get(
            CENTRAL_PROFILE_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            cookies={"session_id": session_id} if session_id else {},
            timeout=CENTRAL_TIMEOUT,
        )
    except requests.RequestException:
        raise SSOServiceError("Central profile service unreachable.", 503)

    if resp.status_code == 401:
        raise SSOServiceError("Invalid or expired access token.", 401)
    if resp.status_code != 200:
        raise SSOServiceError("Unable to fetch central profile.", 502)
    return resp.json()


def get_token_from_request(request):
    """Extract the bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ", 1)[1].strip()


def decode_jwt_payload(token):
    """Decode and validate our own issued JWT, return payload dict or None."""
    try:
        access = AccessToken(token)
        return {"uid": access.get("uid"), "email": access.get("email")}
    except TokenError:
        return None


def profile_to_user_fields(profile, token=None):
    email = profile["email"]
    fields = {
        "central_id": profile["id"],
        "employee_id": profile["employee_id"],
        "name": profile.get("name", ""),
        "email": email,
        "username": email.split("@")[0],
        "phone": profile.get("phone", ""),
        "department": profile.get("department", ""),
        "position": profile.get("position", ""),
        "location": profile.get("address", ""),
        "company": profile.get("company") or profile.get("company_name", ""),
        "avatar_url": profile.get("avatar_url", ""),
        "is_active": True,
    }
    if token is not None:
        fields["central_access_token"] = token
    return fields


def find_user_for_profile(profile):
    employee_id = profile.get("employee_id")
    central_id = profile.get("id")
    email = profile.get("email")

    if employee_id:
        user = User.objects.filter(employee_id=employee_id).first()
        if user:
            return user
    if central_id:
        user = User.objects.filter(central_id=central_id).first()
        if user:
            return user
    if email:
        return User.objects.filter(email__iexact=email).first()
    return None


def sync_user_from_profile(profile, token=None):
    """
    Upsert a local user from a central ERP profile.
    Looks up by employee_id, then central_id, then email.
    Updates only changed fields; creates when no match exists.
    Returns (user, created, changed_field_names).
    """
    fields = profile_to_user_fields(profile, token)
    user = find_user_for_profile(profile)

    if user:
        changed = {k: v for k, v in fields.items() if getattr(user, k) != v}
        if changed:
            for key, value in changed.items():
                setattr(user, key, value)
            user.save(update_fields=list(changed.keys()) + ["updated_at"])
        return user, False, set(changed)

    user = User.objects.create(**fields)
    return user, True, set(fields)
