import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger("apps.feed")


class FeedConsumer(AsyncWebsocketConsumer):
    """
    Real-time feed notifications — tells clients new content is available.
    Client refreshes the REST feed API on receipt.
    """

    async def connect(self):
        self.user = self.scope["user"]
        self.groups = set()

        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        await self.accept()

    async def disconnect(self, code):
        for group in getattr(self, "groups", set()):
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        if data.get("type") == "subscribe":
            await self._subscribe(data)
        elif data.get("type") == "unsubscribe":
            await self._unsubscribe(data)

    async def _subscribe(self, data):
        feed = data.get("feed")
        if feed == "posts":
            await self._join("feed_posts")
        elif feed == "reels":
            await self._join("feed_reels")
        elif feed == "community":
            community_id = data.get("community_id")
            if not community_id:
                return
            if not await self._is_community_member(community_id):
                return
            await self._join(f"feed_community_{community_id}")

    async def _unsubscribe(self, data):
        feed = data.get("feed")
        if feed == "posts":
            await self._leave("feed_posts")
        elif feed == "reels":
            await self._leave("feed_reels")
        elif feed == "community":
            community_id = data.get("community_id")
            if community_id:
                await self._leave(f"feed_community_{community_id}")

    async def _join(self, group):
        if group in self.groups:
            return
        await self.channel_layer.group_add(group, self.channel_name)
        self.groups.add(group)

    async def _leave(self, group):
        if group not in self.groups:
            return
        await self.channel_layer.group_discard(group, self.channel_name)
        self.groups.discard(group)

    async def feed_update(self, event):
        exclude = event.get("exclude_user_id")
        if exclude and str(self.user.id) == exclude:
            return
        await self.send(text_data=json.dumps(event["payload"]))

    @database_sync_to_async
    def _is_community_member(self, community_id):
        from apps.contents.models import CommunityMember

        return CommunityMember.objects.filter(
            user=self.user, community_id=community_id
        ).exists()
