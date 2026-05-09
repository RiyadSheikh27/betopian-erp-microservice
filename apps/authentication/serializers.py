from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    # SSO-sourced fields: optional at registration, will be injected from token later
    designation = serializers.CharField(max_length=100, required=False, allow_blank=True)
    branch = serializers.CharField(max_length=100, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            "email", "username", "full_name", "employee_id",
            "avatar", "bio", "designation", "branch",
            "password", "password_confirm",
        )

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(email=attrs["email"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError({"non_field_errors": "Invalid credentials."})
        if not user.is_active:
            raise serializers.ValidationError({"non_field_errors": "Account is inactive."})
        attrs["user"] = user
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "email", "username", "full_name", "employee_id",
            "avatar", "bio", "designation", "branch", "created_at",
        )
        read_only_fields = ("id", "email", "employee_id", "created_at")

    def get_avatar(self, obj):
        if not obj.avatar:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.avatar.url) if request else obj.avatar.url
