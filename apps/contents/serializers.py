import mimetypes

from django.db import models
from rest_framework import serializers

from .models import Post, PostMedia, Reel

IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"}


def _resolve_media_type(file):
    """Determine media type from file extension."""
    mime, _ = mimetypes.guess_type(file.name)
    if mime is None:
        mime = getattr(file, "content_type", "")
    if mime in IMAGE_TYPES:
        return PostMedia.MediaType.IMAGE, mime
    if mime in VIDEO_TYPES:
        return PostMedia.MediaType.VIDEO, mime
    return None, mime


class PostAuthorSerializer(serializers.Serializer):
    """Author's basic information — mirrors central ERP user fields."""

    id = serializers.UUIDField()
    username = serializers.CharField()
    name = serializers.CharField()
    department = serializers.CharField()
    position = serializers.CharField()
    avatar_url = serializers.URLField()


class PostMediaSerializer(serializers.ModelSerializer):
    """Media item representation."""

    url = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(read_only=True, default=0)
    comment_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = PostMedia
        fields = ("id", "url", "media_type", "caption", "order", "likes_count", "comment_count")

    def get_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class PostSerializer(serializers.ModelSerializer):
    """Read serializer for a post."""

    author = PostAuthorSerializer(read_only=True)
    media = PostMediaSerializer(many=True, read_only=True)
    media_count = serializers.IntegerField(read_only=True)
    likes_count = serializers.IntegerField(read_only=True, default=0)
    comment_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Post
        fields = (
            "id",
            "author",
            "caption",
            "privacy",
            "is_edited",
            "media",
            "media_count",
            "likes_count",
            "comment_count",
            "created_at",
            "updated_at",
        )


class PostCreateSerializer(serializers.ModelSerializer):
    """Create a new post."""

    uploaded_files = serializers.ListField(
        child=serializers.FileField(), write_only=True, required=False
    )
    captions = serializers.ListField(
        child=serializers.CharField(allow_blank=True), write_only=True, required=False
    )

    class Meta:
        model = Post
        fields = ("caption", "privacy", "uploaded_files", "captions")

    def validate_uploaded_files(self, files):
        for file in files:
            media_type, mime = _resolve_media_type(file)
            if media_type is None:
                raise serializers.ValidationError(
                    f"'{file.name}' has unsupported type '{mime}'."
                )
        return files

    def create(self, validated_data):
        """Create post and associated media items."""
        files = validated_data.pop("uploaded_files", [])
        captions = validated_data.pop("captions", [])
        post = Post.objects.create(**validated_data)
        if files:
            PostMedia.objects.bulk_create(
                [
                    PostMedia(
                        post=post,
                        file=file,
                        media_type=_resolve_media_type(file)[0],
                        caption=captions[i] if i < len(captions) else "",
                        order=i,
                    )
                    for i, file in enumerate(files)
                ]
            )
        return post


class PostUpdateSerializer(serializers.ModelSerializer):
    """Update a post. All fields optional — send only what changed."""

    add_files = serializers.ListField(
        child=serializers.FileField(), write_only=True, required=False
    )
    add_captions = serializers.ListField(
        child=serializers.CharField(allow_blank=True), write_only=True, required=False
    )
    remove_media_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )
    edit_media_id = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )
    edit_media_caption = serializers.ListField(
        child=serializers.CharField(allow_blank=True), write_only=True, required=False
    )

    class Meta:
        model = Post
        fields = (
            "caption",
            "privacy",
            "add_files",
            "add_captions",
            "remove_media_ids",
            "edit_media_id",
            "edit_media_caption",
        )

    def validate_add_files(self, files):
        for file in files:
            media_type, mime = _resolve_media_type(file)
            if media_type is None:
                raise serializers.ValidationError(
                    f"'{file.name}' has unsupported type '{mime}'."
                )
        return files

    def validate_remove_media_ids(self, ids):
        existing = set(self.instance.media.values_list("id", flat=True))
        invalid = [str(i) for i in ids if i not in existing]
        if invalid:
            raise serializers.ValidationError(
                f"Media ID(s) not found on this post: {', '.join(invalid)}"
            )
        return ids

    def update(self, instance, validated_data):
        """Update post fields, add new media, remove or edit existing media."""
        add_files = validated_data.pop("add_files", [])
        add_captions = validated_data.pop("add_captions", [])
        remove_ids = validated_data.pop("remove_media_ids", [])
        edit_media_ids = validated_data.pop("edit_media_id", [])
        edit_media_captions = validated_data.pop("edit_media_caption", [])

        if "caption" in validated_data:
            instance.caption = validated_data["caption"]
        if "privacy" in validated_data:
            instance.privacy = validated_data["privacy"]

        if remove_ids:
            instance.media.filter(id__in=remove_ids).delete()

        # Update captions on existing media — positional pairs
        if edit_media_ids:
            media_map = {m.id: m for m in instance.media.filter(id__in=edit_media_ids)}
            to_update = []
            for i, mid in enumerate(edit_media_ids):
                media_obj = media_map.get(mid)
                if media_obj:
                    media_obj.caption = (
                        edit_media_captions[i] if i < len(edit_media_captions) else ""
                    )
                    to_update.append(media_obj)
            if to_update:
                PostMedia.objects.bulk_update(to_update, ["caption"])

        # Append new media - order continues after current max
        if add_files:
            current_max = (
                instance.media.aggregate(max_order=models.Max("order"))["max_order"]
                or -1
            )
            PostMedia.objects.bulk_create(
                [
                    PostMedia(
                        post=instance,
                        file=file,
                        media_type=_resolve_media_type(file)[0],
                        caption=add_captions[i] if i < len(add_captions) else "",
                        order=current_max + 1 + i,
                    )
                    for i, file in enumerate(add_files)
                ]
            )

        instance.is_edited = True
        instance.save(update_fields=["caption", "privacy", "is_edited", "updated_at"])
        return instance


class ReelSerializer(serializers.ModelSerializer):
    """Read serializer for a reel."""

    author = PostAuthorSerializer(read_only=True)
    video_url = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(read_only=True, default=0)
    comment_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Reel
        fields = (
            "id",
            "author",
            "caption",
            "video_url",
            "privacy",
            "view_count",
            "likes_count",
            "comment_count",
            "is_edited",
            "created_at",
            "updated_at",
        )

    def get_video_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.video.url) if request else obj.video.url


class ReelCreateSerializer(serializers.ModelSerializer):
    """Upload a direct reel."""

    class Meta:
        model = Reel
        fields = ("video", "caption", "privacy")

    def validate_video(self, file):
        mime, _ = mimetypes.guess_type(file.name)
        if mime is None:
            mime = getattr(file, "content_type", "")
        if mime not in VIDEO_TYPES:
            raise serializers.ValidationError(
                f"'{file.name}' is not a supported video type."
            )
        return file


class ReelUpdateSerializer(serializers.ModelSerializer):
    """Update reel caption or privacy."""

    class Meta:
        model = Reel
        fields = ("caption", "privacy")

    def update(self, instance, validated_data):
        instance.caption = validated_data.get("caption", instance.caption)
        instance.privacy = validated_data.get("privacy", instance.privacy)
        instance.is_edited = True
        instance.save(update_fields=["caption", "privacy", "is_edited", "updated_at"])
        return instance
