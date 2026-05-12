from rest_framework import serializers

from apps.contents.serializers import PostAuthorSerializer


class NFFeedPostMediaSerializer(serializers.Serializer):
    """Minimal media representation for the news feed."""

    id = serializers.UUIDField()
    url = serializers.SerializerMethodField()
    media_type = serializers.CharField()
    caption = serializers.CharField()
    order = serializers.IntegerField()

    def get_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class NFFeedPostSerializer(serializers.Serializer):
    """
    News feed post shape — mirrors own post list response exactly
    so the client uses one model for both screens.
    """

    id = serializers.UUIDField()
    author = PostAuthorSerializer()
    caption = serializers.CharField()
    privacy = serializers.CharField()
    is_edited = serializers.BooleanField()
    media = NFFeedPostMediaSerializer(many=True)
    media_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def to_representation(self, instance):
        # Push request context down into nested serializers
        self.fields["author"].context.update(self.context)
        self.fields["media"].child.context.update(self.context)
        return super().to_representation(instance)


class NFFeedReelSerializer(serializers.Serializer):
    """Unified reel shape for the feed - covers both"""

    id = serializers.UUIDField()
    source = serializers.CharField()
    author = PostAuthorSerializer()
    caption = serializers.CharField()
    video_url = serializers.SerializerMethodField()
    privacy = serializers.CharField()
    view_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()

    def get_video_url(self, obj):
        # obj is a plain dict built in nf_views; video_url already resolved
        return obj.get("video_url", "")

    def to_representation(self, instance):
        self.fields["author"].context.update(self.context)
        return super().to_representation(instance)
