from .models import ProfileImageStore
from rest_framework import serializers

""" Serializers for Utils Section """


class ProfileImageStoreSerializer(serializers.ModelSerializer):
    """Serializer for ProfileImageStore model."""

    class Meta:
        model = ProfileImageStore
        fields = ("id", "user", "profile_avatar", "created_at")
        read_only_fields = ("id", "created_at", "user")

    def get_url(self, obj):
        request = self.context.get("request")
        return (
            request.build_absolute_uri(obj.profile_avatar.url)
            if request
            else obj.profile_avatar.url
        )
