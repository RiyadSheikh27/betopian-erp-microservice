import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger("apps.chat")


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Handles all real-time chat events for both DM and group conversations.

    Text messages - WebSocket only
    Media/files - HTTP POST then media_sent via WebSocket
    Edit/Delete - WebSocket only
    Reactions - WebSocket only
    Typing/Read - WebSocket only
    Presence - auto on connect/disconnect
    Calling - WebRTC signaling via WebSocket (DM only)
    call_invite - call_accept/call_decline/call_missed
    - offer - answer - ice_candidate - call_end
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
            # Chat
            "message": self._handle_message,
            "media_sent": self._handle_media_sent,
            "typing": self._handle_typing,
            "read": self._handle_read,
            "edit": self._handle_edit,
            "delete": self._handle_delete,
            "react": self._handle_react,
            # Calling
            "call_invite": self._handle_call_invite,
            "call_accept": self._handle_call_accept,
            "call_decline": self._handle_call_decline,
            "call_missed": self._handle_call_missed,
            "call_end": self._handle_call_end,
            # WebRTC signaling
            "offer": self._handle_offer,
            "answer": self._handle_answer,
            "ice_candidate": self._handle_ice_candidate,
        }
        handler = handlers.get(data.get("type"))
        if handler:
            await handler(data)

    # Chat handlers

    async def _handle_message(self, data):
        body = data.get("body", "").strip()
        if not body:
            return
        msg = await self._save_message(body, data.get("reply_to_id"))
        await self.channel_layer.group_send(
            self.room, {"type": "chat_message", "data": msg}
        )

    async def _handle_media_sent(self, data):
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

    # Call handlers

    async def _handle_call_invite(self, data):
        """
        Caller initiates a call.
        Broadcasts ring event to the other participant.
        """
        call_type = data.get("call_type", "audio")  # audio | video
        if call_type not in ("audio", "video"):
            return

        await self.channel_layer.group_send(
            self.room,
            {
                "type": "call_invite",
                "caller_id": str(self.user.id),
                "caller_name": self.user.name,
                "caller_avatar": self.user.avatar_url,
                "call_type": call_type,
            },
        )

    async def _handle_call_accept(self, data):
        """Receiver accepts — notify caller to start WebRTC negotiation."""
        await self.channel_layer.group_send(
            self.room,
            {
                "type": "call_accept",
                "receiver_id": str(self.user.id),
            },
        )

    async def _handle_call_decline(self, data):
        """Receiver declines — save declined call log."""
        call_type = data.get("call_type", "audio")
        await self._save_call_log(call_type, "declined", 0)
        await self.channel_layer.group_send(
            self.room,
            {
                "type": "call_decline",
                "receiver_id": str(self.user.id),
            },
        )

    async def _handle_call_missed(self, data):
        """
        Caller cancels after no answer — save missed call log.
        Called by caller after ring timeout.
        """
        call_type = data.get("call_type", "audio")
        await self._save_call_log(call_type, "missed", 0)
        await self.channel_layer.group_send(
            self.room,
            {
                "type": "call_missed",
                "caller_id": str(self.user.id),
                "call_type": call_type,
            },
        )

    async def _handle_call_end(self, data):
        """
        Either party ends the call.
        Caller/receiver sends duration in seconds.
        """
        call_type = data.get("call_type", "audio")
        duration = int(data.get("duration", 0))
        await self._save_call_log(call_type, "completed", duration)
        await self.channel_layer.group_send(
            self.room,
            {
                "type": "call_end",
                "user_id": str(self.user.id),
                "duration": duration,
            },
        )

    # WebRTC signaling handlers
    # These just relay SDP/ICE between the two peers via the channel group.
    # Server never inspects the WebRTC payload — pure relay.

    async def _handle_offer(self, data):
        """Caller sends SDP offer to receiver."""
        await self.channel_layer.group_send(
            self.room,
            {
                "type": "webrtc_offer",
                "sdp": data.get("sdp"),
                "sender_id": str(self.user.id),
            },
        )

    async def _handle_answer(self, data):
        """Receiver sends SDP answer back to caller."""
        await self.channel_layer.group_send(
            self.room,
            {
                "type": "webrtc_answer",
                "sdp": data.get("sdp"),
                "sender_id": str(self.user.id),
            },
        )

    async def _handle_ice_candidate(self, data):
        """Relay ICE candidate between peers."""
        await self.channel_layer.group_send(
            self.room,
            {
                "type": "webrtc_ice",
                "candidate": data.get("candidate"),
                "sender_id": str(self.user.id),
            },
        )

    # Group - client broadcast handlers
    # These are called when a message is sent to the group.

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

    # Call broadcast handlers
    async def call_invite(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "call_invite",
                    "caller_id": event["caller_id"],
                    "caller_name": event["caller_name"],
                    "caller_avatar": event["caller_avatar"],
                    "call_type": event["call_type"],
                }
            )
        )

    async def call_accept(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "call_accept",
                    "receiver_id": event["receiver_id"],
                }
            )
        )

    async def call_decline(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "call_decline",
                    "receiver_id": event["receiver_id"],
                }
            )
        )

    async def call_missed(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "call_missed",
                    "caller_id": event["caller_id"],
                    "call_type": event["call_type"],
                }
            )
        )

    async def call_end(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "call_end",
                    "user_id": event["user_id"],
                    "duration": event["duration"],
                }
            )
        )

    # WebRTC relay handlers
    async def webrtc_offer(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "offer",
                    "sdp": event["sdp"],
                    "sender_id": event["sender_id"],
                }
            )
        )

    async def webrtc_answer(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "answer",
                    "sdp": event["sdp"],
                    "sender_id": event["sender_id"],
                }
            )
        )

    async def webrtc_ice(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "ice_candidate",
                    "candidate": event["candidate"],
                    "sender_id": event["sender_id"],
                }
            )
        )

    # DB operations

    def _build_url(self, relative_url):
        headers = dict(self.scope.get("headers", []))
        host = headers.get(b"host", b"localhost").decode()
        scheme = "https" if self.scope.get("scheme") in ("wss", "https") else "http"
        return f"{scheme}://{host}{relative_url}"

    @database_sync_to_async
    def _save_call_log(self, call_type, status, duration):
        """Save call as a Message (type=call) + CallLog record."""
        from .models import Message, CallLog, Conversation, ConversationParticipant

        conv = Conversation.objects.get(pk=self.conv_id)

        # Get the other participant
        other = (
            ConversationParticipant.objects.filter(conversation=conv)
            .exclude(user=self.user)
            .select_related("user")
            .first()
        )
        if not other:
            return

        # Build human-readable call message body
        status_labels = {
            "completed": f"{'📹' if call_type == 'video' else '📞'} {call_type.capitalize()} call • {_format_duration(duration)}",
            "missed": f"{'📹' if call_type == 'video' else '📞'} Missed {call_type} call",
            "declined": f"{'📹' if call_type == 'video' else '📞'} {call_type.capitalize()} call declined",
        }
        body = status_labels.get(status, "Call")

        msg = Message.objects.create(
            conversation=conv,
            sender=self.user,
            type=Message.Type.CALL,
            body=body,
        )

        # Determine caller/receiver
        is_caller = status in (
            "missed",
        )  # caller sends missed, receiver sends declined
        caller = self.user if status != "declined" else other.user
        receiver = other.user if status != "declined" else self.user

        CallLog.objects.create(
            conversation=conv,
            caller=caller,
            receiver=receiver,
            call_type=call_type,
            status=status,
            duration=duration,
            message=msg,
        )

        Conversation.objects.filter(pk=self.conv_id).update(
            last_message=msg, last_activity=timezone.now()
        )

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


def _format_duration(seconds):
    """Convert seconds to human readable mm:ss or hh:mm:ss."""
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
