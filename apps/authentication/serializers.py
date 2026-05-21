from rest_framework import serializers
from .models import User


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
