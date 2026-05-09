from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("employee_id", "email", "username", "full_name", "designation", "branch", "is_active", "created_at")
    list_filter = ("is_active", "is_staff", "designation", "branch")
    search_fields = ("email", "username", "full_name", "employee_id")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("username", "full_name", "employee_id", "avatar", "bio")}),
        ("Organisation (SSO)", {"fields": ("designation", "branch")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "full_name", "employee_id", "password1", "password2"),
        }),
    )
