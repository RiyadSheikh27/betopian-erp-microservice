import mimetypes
from django.conf import settings
from rest_framework import serializers
from .models import Conversation, Message, MessageMedia, MessageReaction

""" File type constants """

IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/jpg"}
VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/mov"}
DOC_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

IMAGE_MAX = settings.CHAT_IMAGE_MAX_SIZE_MB * 1024 * 1024
VIDEO_MAX = settings.CHAT_VIDEO_MAX_SIZE_MB * 1024 * 1024
DOC_MAX   = settings.CHAT_DOC_MAX_SIZE_MB   * 1024 * 1024

def resolve_media_type(file):
    """Return (MediaType, mime) tuple. MediaType is None for unsupported files."""
    mime, _ = mimetypes.guess_type(file.name)
    mime = mime or getattr(file, "content_type", "")
    if mime in IMAGE_TYPES:
        return MessageMedia.MediaType.IMAGE, mime
    if mime in VIDEO_TYPES:
        return MessageMedia.MediaType.VIDEO, mime
    if mime in DOC_TYPES:
        return MessageMedia.MediaType.DOC, mime
    return None, mime


""" Conversation serializers """

class ConversationSerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()
    group_name = serializers.SerializerMethodField()
    group_avatar = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
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
        if obj.type != Conversation.Type.DM:
            return None
        me = self.context["request"].user
        other = obj.participants.exclude(user=me).select_related("user").first()
        if not other:
            return None
        return {
            "id": other.user.id,
            "name": other.user.name,
            "avatar_url": other.user.avatar_url,
            "is_online": other.user.is_online,
            "last_seen": other.user.last_seen,
        }

    def get_group_name(self, obj):
        return (
            obj.community.name
            if obj.type == Conversation.Type.GROUP and obj.community
            else None
        )

    def get_group_avatar(self, obj):
        request = self.context.get("request")
        if (
            obj.type == Conversation.Type.GROUP
            and obj.community
            and obj.community.cover_image
            and request
        ):
            return request.build_absolute_uri(obj.community.cover_image.url)
        return None

    def get_last_message(self, obj):
        msg = obj.last_message
        if not msg:
            return None
        return {
            "id": msg.id,
            "sender_name": msg.sender.name,
            "type": msg.type,
            "body": msg.body,
            "created_at": msg.created_at,
        }


""" Message serializers """

class MessageMediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = MessageMedia
        fields = ("id", "url", "media_type", "file_name", "file_size", "order")

    def get_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    reply_to = serializers.SerializerMethodField()
    story = serializers.SerializerMethodField()
    media = MessageMediaSerializer(many=True, read_only=True)
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
            "story",
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

    def get_reply_to(self, obj):
        if not obj.reply_to:
            return None
        return {
            "id": obj.reply_to.id,
            "sender_name": obj.reply_to.sender.name,
            "type": obj.reply_to.type,
            "body": obj.reply_to.body,
        }

    def get_story(self, obj):
        if not obj.story_id:
            return None
        from apps.story.serializers import serialize_story_brief

        return serialize_story_brief(obj.story, self.context.get("request"))

    def get_is_mine(self, obj):
        request = self.context.get("request")
        return bool(request and obj.sender_id == request.user.id)

    def get_reactions(self, obj):
        from django.db.models import Count

        return {
            r["reaction"]: r["count"]
            for r in obj.reactions.values("reaction").annotate(count=Count("id"))
        }


class MediaUploadSerializer(serializers.Serializer):
    """Validates files uploaded via HTTP for media messages."""

    files = serializers.ListField(child=serializers.FileField(), required=True)
    body = serializers.CharField(allow_blank=True, required=False, default="")
    reply_to_id = serializers.UUIDField(required=False, allow_null=True)
    story_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_files(self, files):
        size_map = {
            MessageMedia.MediaType.IMAGE: IMAGE_MAX,
            MessageMedia.MediaType.VIDEO: VIDEO_MAX,
            MessageMedia.MediaType.DOC: DOC_MAX,
        }
        for file in files:
            media_type, mime = resolve_media_type(file)
            if media_type is None:
                raise serializers.ValidationError(
                    f"'{file.name}' is an unsupported file type."
                )
            if file.size > size_map[media_type]:
                raise serializers.ValidationError(
                    f"'{file.name}' exceeds the size limit."
                )
        return files


class MessageReactionDetailSerializer(serializers.ModelSerializer):
    """Used in reaction list endpoint - shows who reacted with what."""

    user_id = serializers.UUIDField(source="user.id")
    name = serializers.CharField(source="user.name")
    avatar_url = serializers.URLField(source="user.avatar_url", allow_null=True)

    class Meta:
        model = MessageReaction
        fields = ("user_id", "name", "avatar_url", "reaction")
