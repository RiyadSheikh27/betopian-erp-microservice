from django.urls import re_path
from .consumers import ChatConsumer, CallConsumer

websocket_urlpatterns = [
    re_path(r"^ws/chat/(?P<conv_id>[0-9a-f-]+)/$", ChatConsumer.as_asgi()),
    re_path(r"^ws/calls/(?P<call_id>[0-9a-f-]+)/$", CallConsumer.as_asgi()),
]