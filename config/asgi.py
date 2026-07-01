import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from apps.chat.middleware import TokenAuthMiddleware
from apps.chat.routing import websocket_urlpatterns as chat_ws
from apps.feed.routing import websocket_urlpatterns as feed_ws
from apps.notifications.routing import websocket_urlpatterns as notify_ws

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": TokenAuthMiddleware(URLRouter(chat_ws + feed_ws + notify_ws)),
    }
)
