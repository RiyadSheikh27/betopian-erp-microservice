from rest_framework import serializers
from .models import User


class SSOLoginSerializer(serializers.Serializer):
    access_token = serializers.CharField(required=False, allow_blank=False)
    id_token = serializers.CharField(required=False, allow_blank=False)
    appVersion = serializers.CharField(required=False, allow_blank=True)
    deviceId = serializers.CharField(required=False, allow_blank=True)
    fcm_token = serializers.CharField(required=False, allow_blank=True)
    platform = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get("access_token") and not attrs.get("id_token"):
            raise serializers.ValidationError(
                "Either access_token or id_token is required."
            )

        fcm_token = (attrs.get("fcm_token") or "").strip()
        platform = (attrs.get("platform") or "").strip().lower()
        device_id = (attrs.get("deviceId") or "").strip()

        if fcm_token or platform:
            errors = {}
            if not fcm_token:
                errors["fcm_token"] = "Required for push notification registration."
            if not device_id:
                errors["deviceId"] = "Required for push notification registration."
            if platform not in ("android", "ios"):
                errors["platform"] = "Use android or ios."
            if errors:
                raise serializers.ValidationError(errors)
            attrs["fcm_token"] = fcm_token
            attrs["platform"] = platform
            attrs["deviceId"] = device_id

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
