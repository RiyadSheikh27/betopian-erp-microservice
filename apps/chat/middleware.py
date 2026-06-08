from urllib.parse import parse_qs
from channels.db import database_sync_to_async
import logging

logger = logging.getLogger("apps.chat")


class TokenAuthMiddleware:
    """
    Authenticates WebSocket connections via JWT token in query string.
    Usage: ws://host/ws/chat/<conv_id>/?token=<bearer_token>
    Decodes JWT to get central ERP uid, looks up local user by central_id.
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
        import jwt

        User = get_user_model()
        try:
            payload = jwt.decode(
                token, options={"verify_signature": False}, algorithms=["HS256"]
            )
            uid = payload.get("uid")
            if not uid:
                return AnonymousUser()
            user = User.objects.get(central_id=uid)
            # Keep central_access_token fresh for any HTTP calls this session
            User.objects.filter(pk=user.pk).update(central_access_token=token)
            logger.info("WS authenticated | user=%s", user.id)
            return user
        except User.DoesNotExist:
            logger.warning("WS auth: user not found | central_id=%s", uid)
        except Exception as e:
            logger.warning("WS auth error | %s", e)
        return AnonymousUser()
