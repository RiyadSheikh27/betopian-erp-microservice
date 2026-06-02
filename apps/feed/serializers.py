from rest_framework import serializers
from apps.contents.serializers import PostAuthorSerializer, CommunitySerializer


class NFFeedPostMediaSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    url = serializers.SerializerMethodField()
    media_type = serializers.CharField()
    caption = serializers.CharField()
    order = serializers.IntegerField()
    like_count = serializers.IntegerField(default=0)
    comment_count = serializers.IntegerField(default=0)
    user_reaction = serializers.CharField(default=None, allow_null=True)
    top_reacts    = serializers.ListField(child=serializers.CharField(), default=list) 

    def get_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class NFFeedPostSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    author = PostAuthorSerializer()
    caption = serializers.CharField()
    privacy = serializers.CharField()
    is_edited = serializers.BooleanField()
    media = NFFeedPostMediaSerializer(many=True)
    media_count = serializers.IntegerField()
    like_count = serializers.IntegerField(default=0)
    comment_count = serializers.IntegerField(default=0)
    user_reaction = serializers.CharField(default=None, allow_null=True)
    top_reacts = serializers.ListField(child=serializers.CharField(), default=list)
    community = CommunitySerializer(read_only=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def to_representation(self, instance):
        self.fields["author"].context.update(self.context)
        self.fields["media"].child.context.update(self.context)
        return super().to_representation(instance)


class NFFeedReelSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    source = serializers.CharField()
    author = PostAuthorSerializer()
    caption = serializers.CharField()
    video_url = serializers.SerializerMethodField()
    privacy = serializers.CharField()
    view_count = serializers.IntegerField()
    like_count = serializers.IntegerField(default=0)
    comment_count = serializers.IntegerField(default=0)
    user_reaction = serializers.CharField(default=None, allow_null=True)
    top_reacts = serializers.ListField(child=serializers.CharField(), default=list)
    created_at = serializers.DateTimeField()

    def get_video_url(self, obj):
        return obj.get("video_url", "")

    def to_representation(self, instance):
        self.fields["author"].context.update(self.context)
        return super().to_representation(instance)


class NFFeedCommunitySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    source = serializers.CharField()
    author = PostAuthorSerializer()
    caption = serializers.CharField()
    video_url = serializers.SerializerMethodField()
    privacy = serializers.CharField()
    view_count = serializers.IntegerField()
    like_count = serializers.IntegerField(default=0)
    comment_count = serializers.IntegerField(default=0)
    user_reaction = serializers.CharField(default=None, allow_null=True)
    top_reacts = serializers.ListField(child=serializers.CharField(), default=list)
    created_at = serializers.DateTimeField()

    def get_video_url(self, obj):
        return obj.get("video_url", "")

    def to_representation(self, instance):
        self.fields["author"].context.update(self.context)
        return super().to_representation(instance)
