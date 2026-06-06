import mimetypes
from django.conf import settings
from rest_framework import serializers
from .models import (
    Conversation,
    ConversationParticipant,
    Message,
    MessageMedia,
    MessageReaction,
    MessageStatus,
)

DOC_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"}

DOC_MAX_SIZE = settings.DOC_MAX_SIZE
IMAGE_MAX_SIZE = settings.IMAGE_MAX_SIZE
VIDEO_MAX_SIZE = settings.VIDEO_MAX_SIZE


def _resolve_media_type(file):
    mime, _ = mimetypes.guess_type(file.name)
    if not mime:
        mime = getattr(file, "content_type", "")
    if mime in IMAGE_TYPES:
        return MessageMedia.MediaType.IMAGE, mime
    if mime in VIDEO_TYPES:
        return MessageMedia.MediaType.VIDEO, mime
    if mime in DOC_TYPES:
        return MessageMedia.MediaType.DOC, mime
    return None, mime


class ConversationParticipantSerializer(serializers.Serializer):
    """Used in group info - full participant list."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    avatar_url = serializers.URLField(allow_null=True)
    is_online = serializers.BooleanField()
    last_seen = serializers.DateTimeField(allow_null=True)


class LastMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.name")

    class Meta:
        model = Message
        fields = ("id", "sender_name", "type", "body", "created_at")


class ConversationSerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()
    group_name = serializers.SerializerMethodField()
    group_avatar = serializers.SerializerMethodField()
    last_message = LastMessageSerializer(read_only=True)
    unread_count = serializers.IntegerField(read_only=True, default=0)
    participant_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Conversation
        fields = (
            "id",
            "type",
            "other_user",
            "group_name",
            "group_avatar",
            "last_message",
            "unread_count",
            "participant_count",
            "last_activity",
        )

    def get_other_user(self, obj):
        if obj.type != Conversation.ConversationType.DM:
            return None
        request = self.context["request"]
        other = (
            obj.participants.exclude(user=request.user).select_related("user").first()
        )
        if not other:
            return None
        return {
            "id": other.user.id,
            "name": other.user.name,
            "avatar_url": other.user.avatar_url,
            "is_online": other.is_online,
            "last_seen": other.last_seen,
        }

    def get_group_name(self, obj):
        if obj.type != Conversation.ConversationType.GROUP:
            return None
        return obj.community.name if obj.community else None

    def get_group_avatar(self, obj):
        if obj.type != Conversation.ConversationType.GROUP:
            return None
        request = self.context.get("request")
        if obj.community and obj.community.cover_image and request:
            return request.build_absolute_uri(obj.community.cover_image.url)
        return None


class MessageMediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = MessageMedia
        fields = ("id", "url", "media_type", "file_name", "file_size", "order")

    def get_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class ReplySnippetSerializer(serializers.ModelSerializer):
    """Minimal reply preview - no deep nesting."""

    sender_name = serializers.CharField(source="sender.name")

    class Meta:
        model = Message
        fields = ("id", "sender_name", "type", "body")


class MessageReactionDetailSerializer(serializers.ModelSerializer):
    """Single reactor - used in reaction list view."""

    user_id = serializers.UUIDField(source="user.id")
    name = serializers.CharField(source="user.name")
    avatar_url = serializers.URLField(source="user.avatar_url", allow_null=True)
    reaction = serializers.CharField()

    class Meta:
        model = MessageReaction
        fields = ("user_id", "name", "avatar_url", "reaction")


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    media = MessageMediaSerializer(many=True, read_only=True)
    reply_to = ReplySnippetSerializer(read_only=True)
    reactions = serializers.SerializerMethodField()
    read_by_count = serializers.IntegerField(read_only=True, default=0)
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "sender",
            "type",
            "body",
            "reply_to",
            "media",
            "reactions",
            "read_by_count",
            "is_edited",
            "is_deleted",
            "is_mine",
            "created_at",
            "updated_at",
        )

    def get_sender(self, obj):
        return {
            "id": obj.sender.id,
            "name": obj.sender.name,
            "avatar_url": obj.sender.avatar_url,
        }

    def get_is_mine(self, obj):
        request = self.context.get("request")
        return request and obj.sender_id == request.user.id

    def get_reactions(self, obj):
        """Returns summary: {love: 2, haha: 1} - detail list via separate endpoint."""
        from django.db.models import Count

        qs = obj.reactions.values("reaction").annotate(count=Count("id"))
        return {r["reaction"]: r["count"] for r in qs}


class MessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(allow_blank=True, required=False, default="")
    reply_to_id = serializers.UUIDField(required=False, allow_null=True)
    files = serializers.ListField(
        child=serializers.FileField(), required=False, default=list
    )

    def validate(self, data):
        if not data.get("body") and not data.get("files"):
            raise serializers.ValidationError("Message must have text or files.")
        return data

    def validate_files(self, files):
        for file in files:
            media_type, mime = _resolve_media_type(file)
            if media_type is None:
                raise serializers.ValidationError(f"'{file.name}' unsupported type.")
            limits = {
                MessageMedia.MediaType.IMAGE: IMAGE_MAX_SIZE,
                MessageMedia.MediaType.VIDEO: VIDEO_MAX_SIZE,
                MessageMedia.MediaType.DOC: DOC_MAX_SIZE,
            }
            if file.size > limits[media_type]:
                raise serializers.ValidationError(f"'{file.name}' exceeds size limit.")
        return files
