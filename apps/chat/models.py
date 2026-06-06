import uuid
from django.conf import settings
from django.db import models
from apps.utils.models import TimeStampedModel


class Conversation(TimeStampedModel):
    """
    DM: exactly 2 participants, community=None
    Group: community FK set, participants = all community members
    """

    class ConversationType(models.TextChoices):
        DM = "dm", "Direct Message"
        GROUP = "group", "Group"

    type = models.CharField(max_length=10, choices=ConversationType.choices)
    community = models.OneToOneField(
        "contents.Community",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="conversation",
    )
    last_message = models.ForeignKey(
        "Message",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    last_activity = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta(TimeStampedModel.Meta):
        db_table = "conversations"
        indexes = [
            models.Index(fields=["-last_activity"], name="idx_conv_last_activity"),
        ]


class ConversationParticipant(TimeStampedModel):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations"
    )
    last_read_message = models.ForeignKey(
        "Message", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    last_seen = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(default=False)

    class Meta(TimeStampedModel.Meta):
        db_table = "conversation_participants"
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"], name="unique_conversation_participant"
            )
        ]
        indexes = [
            models.Index(fields=["user", "conversation"], name="idx_cp_user_conv"),
        ]


class Message(TimeStampedModel):
    class MessageType(models.TextChoices):
        TEXT = "text", "Text"
        MEDIA = "media", "Media"
        DOC = "doc", "Document"
        DELETED = "deleted", "Deleted"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages"
    )
    type = models.CharField(
        max_length=10, choices=MessageType.choices, default=MessageType.TEXT
    )
    body = models.TextField(blank=True)
    reply_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replies"
    )
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    class Meta(TimeStampedModel.Meta):
        db_table = "messages"
        indexes = [
            models.Index(
                fields=["conversation", "-created_at", "-id"],
                name="idx_msg_conv_created",
            ),
        ]


class MessageMedia(TimeStampedModel):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        DOC = "doc", "Document"

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="media")
    file = models.FileField(upload_to="chat_media/%Y/%m/%d/")
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta(TimeStampedModel.Meta):
        db_table = "message_media"
        ordering = ["order"]


class MessageReaction(TimeStampedModel):
    """One reaction per user per message."""

    class Reaction(models.TextChoices):
        LOVE = "love", "Love"
        ANGRY = "angry", "Angry"
        HAHA = "haha", "Haha"
        WOW = "wow", "Wow"
        SAD = "sad", "Sad"
        CARE = "care", "Care"

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="reactions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_reactions",
    )
    reaction = models.CharField(max_length=10, choices=Reaction.choices)

    class Meta(TimeStampedModel.Meta):
        db_table = "message_reactions"
        constraints = [
            models.UniqueConstraint(
                fields=["message", "user"], name="unique_msg_reaction"
            )
        ]
        indexes = [
            models.Index(fields=["message", "reaction"], name="idx_msgreact_msg"),
        ]


class MessageStatus(TimeStampedModel):
    """Per-recipient delivery + read status."""

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="statuses"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_statuses",
    )
    is_delivered = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta(TimeStampedModel.Meta):
        db_table = "message_statuses"
        constraints = [
            models.UniqueConstraint(
                fields=["message", "recipient"], name="unique_msg_status"
            )
        ]
        indexes = [
            models.Index(
                fields=["recipient", "is_read"], name="idx_msgstatus_recipient_read"
            ),
            models.Index(fields=["message"], name="idx_msgstatus_message"),
        ]
