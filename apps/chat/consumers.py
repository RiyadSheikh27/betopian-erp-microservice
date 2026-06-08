import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger("apps.chat")


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Handles all real-time chat events for both DM and group conversations.

    Text messages - sent and received entirely via WebSocket
    Media/files - uploaded via HTTP POST, then notified via WebSocket (media_sent)
    Edit / Delete - via WebSocket only
    Reactions - via WebSocket only
    Typing / Read - via WebSocket only
    Presence - auto on connect/disconnect
    """

    async def connect(self):
        self.conv_id = self.scope["url_route"]["kwargs"]["conv_id"]
        self.room = f"chat_{self.conv_id}"
        self.user = self.scope["user"]

        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        if not await self._is_participant():
            await self.close()
            return

        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()
        await self._set_online(True)
        await self.channel_layer.group_send(
            self.room,
            {"type": "presence", "user_id": str(self.user.id), "is_online": True},
        )

    async def disconnect(self, code):
        if not hasattr(self, "room") or not self.user or not self.user.is_authenticated:
            return
        await self.channel_layer.group_discard(self.room, self.channel_name)
        await self._set_online(False)
        await self.channel_layer.group_send(
            self.room,
            {
                "type": "presence",
                "user_id": str(self.user.id),
                "is_online": False,
                "last_seen": timezone.now().isoformat(),
            },
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        handlers = {
            "message": self._handle_message,
            "media_sent": self._handle_media_sent,
            "typing": self._handle_typing,
            "read": self._handle_read,
            "edit": self._handle_edit,
            "delete": self._handle_delete,
            "react": self._handle_react,
        }
        handler = handlers.get(data.get("type"))
        if handler:
            await handler(data)

    # Event handlers

    async def _handle_message(self, data):
        body = data.get("body", "").strip()
        if not body:
            return
        msg = await self._save_message(body, data.get("reply_to_id"))
        await self.channel_layer.group_send(
            self.room, {"type": "chat_message", "data": msg}
        )

    async def _handle_media_sent(self, data):
        """Called after client uploads media via HTTP — broadcasts to group."""
        msg_id = data.get("message_id")
        if not msg_id:
            return
        msg = await self._fetch_message(msg_id)
        if msg:
            await self.channel_layer.group_send(
                self.room, {"type": "chat_message", "data": msg}
            )

    async def _handle_typing(self, data):
        await self.channel_layer.group_send(
            self.room,
            {
                "type": "typing",
                "user_id": str(self.user.id),
                "is_typing": data.get("is_typing", False),
            },
        )

    async def _handle_read(self, data):
        msg_id = data.get("message_id")
        if not msg_id:
            return
        await self._mark_read(msg_id)
        await self.channel_layer.group_send(
            self.room,
            {
                "type": "read_receipt",
                "user_id": str(self.user.id),
                "message_id": msg_id,
            },
        )

    async def _handle_edit(self, data):
        msg_id = data.get("message_id")
        body = data.get("body", "").strip()
        if not msg_id or not body:
            return
        if await self._edit_message(msg_id, body):
            await self.channel_layer.group_send(
                self.room,
                {
                    "type": "message_edited",
                    "data": {"id": msg_id, "body": body, "is_edited": True},
                },
            )

    async def _handle_delete(self, data):
        msg_id = data.get("message_id")
        if not msg_id:
            return
        if await self._delete_message(msg_id):
            await self.channel_layer.group_send(
                self.room,
                {
                    "type": "message_deleted",
                    "data": {
                        "id": msg_id,
                        "type": "deleted",
                        "body": "This message was deleted",
                    },
                },
            )

    async def _handle_react(self, data):
        msg_id = data.get("message_id")
        reaction = data.get("reaction", "").lower()
        if not msg_id or not reaction:
            return
        result = await self._toggle_reaction(msg_id, reaction)
        if result:
            await self.channel_layer.group_send(
                self.room, {"type": "reaction_updated", "data": result}
            )

    # Group - client broadcast handlers

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps({"type": "message", "data": event["data"]})
        )

    async def typing(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",
                    "user_id": event["user_id"],
                    "is_typing": event["is_typing"],
                }
            )
        )

    async def presence(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "presence",
                    "user_id": event["user_id"],
                    "is_online": event["is_online"],
                    "last_seen": event.get("last_seen"),
                }
            )
        )

    async def read_receipt(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "read_receipt",
                    "user_id": event["user_id"],
                    "message_id": event["message_id"],
                }
            )
        )

    async def message_edited(self, event):
        await self.send(
            text_data=json.dumps({"type": "message_edited", "data": event["data"]})
        )

    async def message_deleted(self, event):
        await self.send(
            text_data=json.dumps({"type": "message_deleted", "data": event["data"]})
        )

    async def reaction_updated(self, event):
        await self.send(
            text_data=json.dumps({"type": "reaction_updated", "data": event["data"]})
        )

    # DB operations 
    def _build_url(self, relative_url):
        """Build absolute URL from relative media path."""
        from django.conf import settings

        host = self.scope.get("server", ("localhost", 8000))
        scheme = "https" if self.scope.get("scheme") == "wss" else "http"
        base = f"{scheme}://{host[0]}:{host[1]}"
        return f"{base}{relative_url}"

    @database_sync_to_async
    def _save_message(self, body, reply_to_id=None):
        from .models import (
            Message,
            MessageStatus,
            ConversationParticipant,
            Conversation,
        )

        msg = Message.objects.create(
            conversation_id=self.conv_id,
            sender=self.user,
            type=Message.Type.TEXT,
            body=body,
            reply_to_id=reply_to_id,
        )

        # Status rows for DM only
        conv = Conversation.objects.get(pk=self.conv_id)
        if conv.type == Conversation.Type.DM:
            other_ids = list(
                ConversationParticipant.objects.filter(conversation_id=self.conv_id)
                .exclude(user=self.user)
                .values_list("user_id", flat=True)
            )
            MessageStatus.objects.bulk_create(
                [MessageStatus(message=msg, recipient_id=uid) for uid in other_ids]
            )

        Conversation.objects.filter(pk=self.conv_id).update(
            last_message=msg, last_activity=timezone.now()
        )

        reply_data = None
        if reply_to_id:
            try:
                reply = Message.objects.select_related("sender").get(pk=reply_to_id)
                reply_data = {
                    "id": str(reply.id),
                    "sender_name": reply.sender.name,
                    "type": reply.type,
                    "body": reply.body,
                }
            except Message.DoesNotExist:
                pass

        return {
            "id": str(msg.id),
            "sender": {
                "id": str(self.user.id),
                "name": self.user.name,
                "avatar_url": self.user.avatar_url,
            },
            "type": msg.type,
            "body": msg.body,
            "reply_to": reply_data,
            "media": [],
            "reactions": {},
            "read_by_count": 0,
            "is_edited": False,
            "is_deleted": False,
            "created_at": msg.created_at.isoformat(),
            "updated_at": msg.updated_at.isoformat(),
        }

    @database_sync_to_async
    def _fetch_message(self, msg_id):
        """Fetch a message with full media — used after HTTP media upload."""
        from .models import Message

        try:
            msg = (
                Message.objects.select_related("sender", "reply_to__sender")
                .prefetch_related("media")
                .get(pk=msg_id, conversation_id=self.conv_id)
            )
            return {
                "id": str(msg.id),
                "sender": {
                    "id": str(msg.sender.id),
                    "name": msg.sender.name,
                    "avatar_url": msg.sender.avatar_url,
                },
                "type": msg.type,
                "body": msg.body,
                "reply_to": (
                    {
                        "id": str(msg.reply_to.id),
                        "sender_name": msg.reply_to.sender.name,
                        "type": msg.reply_to.type,
                        "body": msg.reply_to.body,
                    }
                    if msg.reply_to
                    else None
                ),
                "media": [
                    {
                        "id": str(m.id),
                        "url": self._build_url(m.file.url),
                        "media_type": m.media_type,
                        "file_name": m.file_name,
                        "file_size": m.file_size,
                        "order": m.order,
                    }
                    for m in msg.media.all()
                ],
                "reactions": {},
                "read_by_count": 0,
                "is_edited": msg.is_edited,
                "is_deleted": msg.is_deleted,
                "created_at": msg.created_at.isoformat(),
                "updated_at": msg.updated_at.isoformat(),
            }
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def _edit_message(self, msg_id, body):
        from .models import Message

        return bool(
            Message.objects.filter(
                pk=msg_id,
                sender=self.user,
                is_deleted=False,
                type=Message.Type.TEXT,
            ).update(body=body, is_edited=True)
        )

    @database_sync_to_async
    def _delete_message(self, msg_id):
        from .models import Message, MessageMedia

        try:
            msg = Message.objects.get(pk=msg_id, sender=self.user, is_deleted=False)
            msg.body = "This message was deleted"
            msg.type = Message.Type.DELETED
            msg.is_deleted = True
            msg.save(update_fields=["body", "type", "is_deleted", "updated_at"])
            MessageMedia.objects.filter(message=msg).delete()
            return True
        except Message.DoesNotExist:
            return False

    @database_sync_to_async
    def _toggle_reaction(self, msg_id, reaction):
        from .models import MessageReaction
        from django.db.models import Count

        if reaction not in MessageReaction.Reaction.values:
            return None

        existing = MessageReaction.objects.filter(
            message_id=msg_id, user=self.user
        ).first()
        if existing:
            if existing.reaction == reaction:
                existing.delete()
                reaction, reacted = None, False
            else:
                existing.reaction = reaction
                existing.save(update_fields=["reaction", "updated_at"])
                reacted = True
        else:
            MessageReaction.objects.create(
                message_id=msg_id, user=self.user, reaction=reaction
            )
            reacted = True

        counts = {
            r["reaction"]: r["count"]
            for r in MessageReaction.objects.filter(message_id=msg_id)
            .values("reaction")
            .annotate(count=Count("id"))
        }
        return {
            "message_id": str(msg_id),
            "reacted": reacted,
            "reaction": reaction,
            "counts": counts,
        }

    @database_sync_to_async
    def _is_participant(self):
        from .models import ConversationParticipant

        return ConversationParticipant.objects.filter(
            conversation_id=self.conv_id, user=self.user
        ).exists()

    @database_sync_to_async
    def _set_online(self, status):
        from django.contrib.auth import get_user_model

        get_user_model().objects.filter(pk=self.user.pk).update(
            is_online=status,
            **({"last_seen": timezone.now()} if not status else {}),
        )

    @database_sync_to_async
    def _mark_read(self, message_id):
        from .models import MessageStatus

        MessageStatus.objects.filter(
            message_id=message_id, recipient=self.user, is_read=False
        ).update(is_read=True, is_delivered=True, read_at=timezone.now())
