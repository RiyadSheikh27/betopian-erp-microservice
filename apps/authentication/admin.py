from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-created_at",)

    list_display = (
        "employee_id",
        "username",
        "email",
        "name",
        "department",
        "position",
        "location",
        "company",
        "is_staff",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_staff",
        "is_active",
        "is_superuser",
        "department",
        "position",
        "location",
        "company",
        "created_at",
    )

    search_fields = (
        "employee_id",
        "username",
        "email",
        "name",
        "phone",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "last_login",
    )

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "central_id",
                    "id",
                    "employee_id",
                    "username",
                    "email",
                    "name",
                    "phone",
                    "location",
                    "company",
                    "department",
                    "position",
                    "avatar_url",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Authentication",
            {
                "fields": (
                    "central_access_token",
                    "last_login",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    add_fieldsets = ()

    filter_horizontal = (
        "groups",
        "user_permissions",
    )

    def has_add_permission(self, request):
        return False
