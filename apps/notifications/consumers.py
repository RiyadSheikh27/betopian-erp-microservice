import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger("apps.notifications")


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Real-time notification channel.
    Events use a consistent envelope for future Firebase mirroring.
    """

    async def connect(self):
        self.user = self.scope["user"]
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.group = f"notify_{self.user.id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def notification_event(self, event):
        await self.send(text_data=json.dumps(event["envelope"]))
