from rest_framework import serializers
from .models import User


class SSOLoginSerializer(serializers.Serializer):
    access_token = serializers.CharField(required=False, allow_blank=False)
    id_token = serializers.CharField(required=False, allow_blank=False)
    appVersion = serializers.CharField(required=False, allow_blank=True)
    deviceId = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get("access_token") and not attrs.get("id_token"):
            raise serializers.ValidationError(
                "Either access_token or id_token is required."
            )
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    """Read-only profile serializer."""

    class Meta:
        model = User
        fields = (
            "id",
            "central_id",
            "employee_id",
            "name",
            "email",
            "username",
            "phone",
            "department",
            "position",
            "location",
            "company",
            "avatar_url",
        )
        read_only_fields = fields
