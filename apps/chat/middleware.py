from urllib.parse import parse_qs
from channels.db import database_sync_to_async
import logging

logger = logging.getLogger("apps.chat")


class TokenAuthMiddleware:
    """
    Authenticates WebSocket connections via JWT token in query string.
    Usage: ws://host/ws/chat/<conv_id>/?token=<app_access_token>
    Uses the same app JWT lookup as REST (email claim).
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        from django.contrib.auth.models import AnonymousUser

        token = parse_qs(scope.get("query_string", b"").decode()).get("token", [None])[
            0
        ]
        scope["user"] = await self._get_user(token) if token else AnonymousUser()
        return await self.inner(scope, receive, send)

    @database_sync_to_async
    def _get_user(self, token):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import AnonymousUser
        from apps.authentication.utils import decode_jwt_payload

        User = get_user_model()
        payload = decode_jwt_payload(token)
        if not payload or not payload.get("email"):
            return AnonymousUser()

        user = User.objects.filter(email__iexact=payload["email"]).first()
        if not user:
            logger.warning("WS auth: user not found | email=%s", payload["email"])
            return AnonymousUser()

        logger.info("WS authenticated | user=%s", user.id)
        return user
