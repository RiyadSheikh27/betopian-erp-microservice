from rest_framework import serializers
from .models import Like, Comment

""" LIKE SECTION'S SERIALIZERS """


class LikerSerializer(serializers.ModelSerializer):
    """Reactor list item — user info + reaction name."""
    user_id     = serializers.UUIDField(source="user.id")
    employee_id = serializers.CharField(source="user.employee_id")
    name        = serializers.CharField(source="user.name")
    avatar_url  = serializers.URLField(source="user.avatar_url")
    reaction    = serializers.CharField()

    class Meta:
        model  = Like
        fields = ("user_id", "employee_id", "name", "avatar_url", "reaction")


class LikeResponseSerializer(serializers.Serializer):
    liked = serializers.BooleanField()
    like_count = serializers.IntegerField()


""" COMMENT SECTION'S SERIALIZERS """


class CommentAuthorSerializer(serializers.Serializer):
    """Minimal author info on each comment."""

    user_id = serializers.UUIDField(source="id")
    central_id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    avatar_url = serializers.URLField()


class CommentSerializer(serializers.ModelSerializer):
    author = CommentAuthorSerializer(source="user", read_only=True)
    replies = serializers.SerializerMethodField()
    reply_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Comment
        fields = (
            "id",
            "author",
            "body",
            "parent",
            "reply_count",
            "replies",
            "created_at",
            "updated_at",
        )

    def get_replies(self, obj):
        replies = getattr(obj, "_replies", [])
        return CommentSerializer(replies, many=True, context=self.context).data


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ("body", "parent")

    def validate_parent(self, parent):
        if parent is None:
            return parent
        # Parent must belong to the same target
        ct = self.context["content_type"]
        obj_id = self.context["object_id"]
        if parent.content_type != ct or str(parent.object_id) != str(obj_id):
            raise serializers.ValidationError(
                "Parent comment does not belong to this target."
            )
        return parent


class CommentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ("body",)

    def update(self, instance, validated_data):
        instance.body = validated_data["body"]
        instance.save(update_fields=["body", "updated_at"])
        return instance
