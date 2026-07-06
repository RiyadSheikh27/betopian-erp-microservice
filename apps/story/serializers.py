import mimetypes

from rest_framework import serializers

from apps.utils.media import compress_image, validate_file_size, validate_video_duration
from .models import Story

IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/jpg"}
VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/mov"}


def resolve_media_type(file):
    mime, _ = mimetypes.guess_type(file.name)
    mime = mime or getattr(file, "content_type", "")
    if mime in IMAGE_TYPES:
        return Story.MediaType.IMAGE, mime
    if mime in VIDEO_TYPES:
        return Story.MediaType.VIDEO, mime
    return None, mime


def build_file_url(request, file_field, url_builder=None):
    if not file_field:
        return None
    if url_builder:
        return url_builder(file_field.url)
    if request:
        return request.build_absolute_uri(file_field.url)
    return file_field.url


def story_preview_url(story, request=None, url_builder=None):
    if story.thumbnail:
        return build_file_url(request, story.thumbnail, url_builder)
    if story.media_type == Story.MediaType.IMAGE:
        return build_file_url(request, story.file, url_builder)
    return None


def serialize_story_brief(story, request=None, url_builder=None):
    author = story.author
    return {
        "id": str(story.id),
        "media_type": story.media_type,
        "media_url": build_file_url(request, story.file, url_builder),
        "thumbnail_url": build_file_url(request, story.thumbnail, url_builder),
        "preview_url": story_preview_url(story, request, url_builder),
        "author": {
            "id": str(author.id),
            "name": author.name,
            "avatar_url": author.avatar_url or "",
        },
    }


def get_active_story(story_id):
    from django.utils import timezone

    return Story.objects.select_related("author").get(
        pk=story_id,
        expires_at__gt=timezone.now(),
    )


class StorySerializer(serializers.ModelSerializer):
    media_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    like_count = serializers.IntegerField(read_only=True, default=0)
    viewer_count = serializers.IntegerField(read_only=True, default=0)
    user_reaction = serializers.CharField(read_only=True, default=None, allow_null=True)
    top_reacts = serializers.ListField(
        child=serializers.CharField(), read_only=True, default=list
    )
    is_active = serializers.SerializerMethodField()
    is_viewed = serializers.BooleanField(read_only=True, default=False)
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = (
            "id",
            "media_type",
            "media_url",
            "thumbnail_url",
            "preview_url",
            "expires_at",
            "is_active",
            "like_count",
            "viewer_count",
            "user_reaction",
            "top_reacts",
            "is_viewed",
            "is_mine",
            "created_at",
        )

    def get_media_url(self, obj):
        return build_file_url(self.context.get("request"), obj.file)

    def get_thumbnail_url(self, obj):
        return build_file_url(self.context.get("request"), obj.thumbnail)

    def get_preview_url(self, obj):
        return story_preview_url(obj, self.context.get("request"))

    def get_is_active(self, obj):
        return obj.is_active

    def get_is_mine(self, obj):
        request = self.context.get("request")
        return bool(request and obj.author_id == request.user.id)

    def _is_owner(self, obj):
        request = self.context.get("request")
        return bool(request and obj.author_id == request.user.id)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get("include_preview_url", True):
            data.pop("preview_url", None)
        if not self._is_owner(instance):
            data["like_count"] = None
            data["viewer_count"] = None
            data["top_reacts"] = None
        return data


class StoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Story
        fields = ("file",)

    def validate_file(self, file):
        media_type, mime = resolve_media_type(file)
        if not media_type:
            raise serializers.ValidationError(
                f"'{file.name}' is not a supported image or video type."
            )

        try:
            validate_file_size(file, media_type)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

        if media_type == Story.MediaType.VIDEO:
            try:
                validate_video_duration(file)
            except ValueError as exc:
                raise serializers.ValidationError(str(exc)) from exc
        else:
            file = compress_image(file)

        self._media_type = media_type
        return file

    def create(self, validated_data):
        return Story.objects.create(
            author=self.context["request"].user,
            file=validated_data["file"],
            media_type=self._media_type,
        )


class StoryViewerSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    name = serializers.CharField()
    avatar_url = serializers.URLField(allow_null=True)
    viewed_at = serializers.DateTimeField()
