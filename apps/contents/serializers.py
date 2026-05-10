from django.db import models
from rest_framework import serializers
from .models import Post, PostMedia
import mimetypes

""" Helper Function """

def _resolve_media_type(file):
    """Determine media type from file extension"""

    IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"}

    mime, _ = mimetypes.guess_type(file.name)
    if mime is None:
        mime = getattr(file, "content_type", "")

    if mime in IMAGE_TYPES:
        return PostMedia.MediaType.IMAGE, mime
    if mime in VIDEO_TYPES:
        return PostMedia.MediaType.VIDEO, mime
    return None, mime  # unsupported

""" Serializers for Contents Section """

class PostMediaSerializer(serializers.ModelSerializer):
    """ Media Handling Seciton """
    url = serializers.SerializerMethodField()

    class Meta:
        model = PostMedia
        fields = ("id", "url", "media_type", "order")

    def get_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class PostAuthorSerializer(serializers.Serializer):
    """Author's Basic Information"""

    id = serializers.UUIDField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    designation = serializers.CharField()
    branch = serializers.CharField()
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, obj):
        if not obj.avatar:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.avatar.url) if request else obj.avatar.url


class PostSerializer(serializers.ModelSerializer):
    """ List of Posts Serializer"""
    author = PostAuthorSerializer(read_only=True)
    media = PostMediaSerializer(many=True, read_only=True)
    media_count = serializers.IntegerField(read_only=True)

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
            "created_at",
            "updated_at",
        )


class PostCreateSerializer(serializers.ModelSerializer):
    """ Create New Post Serializer"""
    uploaded_files = serializers.ListField(
        child=serializers.FileField(), write_only=True, required=False
    )

    class Meta:
        model = Post
        fields = ("caption", "uploaded_files")

    def validate_uploaded_files(self, files):
        for file in files:
            media_type, mime = _resolve_media_type(file)
            if media_type is None:
                raise serializers.ValidationError(
                    f"'{file.name}' has unsupported type '{mime}'."
                )
        return files

    def create(self, validated_data):
        files = validated_data.pop("uploaded_files", [])
        post = Post.objects.create(**validated_data)
        self._bulk_create_media(post, files)
        return post

    def _bulk_create_media(self, post, files):
        if not files:
            return
        PostMedia.objects.bulk_create(
            [
                PostMedia(
                    post=post,
                    file=file,
                    media_type=_resolve_media_type(file)[0],
                    order=index,
                )
                for index, file in enumerate(files)
            ]
        )


class PostUpdateSerializer(serializers.ModelSerializer):
    """ Update a Post Including Media Files"""
    add_files = serializers.ListField(
        child=serializers.FileField(), write_only=True, required=False
    )
    remove_media_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )

    class Meta:
        model = Post
        fields = ("caption", "privacy", "add_files", "remove_media_ids")

    def validate_add_files(self, files):
        for file in files:
            media_type, mime = _resolve_media_type(file)
            if media_type is None:
                raise serializers.ValidationError(
                    f"'{file.name}' has unsupported type '{mime}'."
                )
        return files

    def validate_remove_media_ids(self, ids):
        # Ensure all supplied IDs actually belong to this post
        existing_ids = set(self.instance.media.values_list("id", flat=True))
        invalid = [str(i) for i in ids if i not in existing_ids]
        if invalid:
            raise serializers.ValidationError(
                f"Media ID(s) not found on this post: {', '.join(invalid)}"
            )
        return ids

    def update(self, instance, validated_data):
        add_files = validated_data.pop("add_files", [])
        remove_ids = validated_data.pop("remove_media_ids", [])

        # Update caption if provided
        if "caption" in validated_data:
            instance.caption = validated_data["caption"]

        # Delete requested media in a single query
        if remove_ids:
            instance.media.filter(id__in=remove_ids).delete()

        # Append new media — order starts after current max to avoid conflicts
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
                        order=current_max + 1 + index,
                    )
                    for index, file in enumerate(add_files)
                ]
            )

        instance.is_edited = True
        instance.save(update_fields=["caption", "privacy", "is_edited", "updated_at"])
        return instance


class CursorPaginatedPostSerializer(serializers.Serializer):
    """Wraps post list with cursor metadata for infinite scroll."""

    posts = PostSerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)
    has_more = serializers.BooleanField()
