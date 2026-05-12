from rest_framework import serializers
from .models import User


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Read-only profile serializer.
    Central ERP owns all user data - no write operations from this service.
    avatar_url is an external URL from central ERP, returned as-is.
    """
    class Meta:
        model        = User
        fields       = (
            "id", "employee_id", "name", "email",
            "username", "phone", "department", "position", "avatar_url",
        )
        read_only_fields = fields
