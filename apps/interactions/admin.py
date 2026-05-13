from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import Like


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "content_type",
        "object_id",
        "content_object_display",
        "created_at",
    )

    list_filter = (
        "content_type",
        "created_at",
    )

    search_fields = (
        "user__username",
        "user__email",
        "object_id",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "content_object",
    )

    autocomplete_fields = ("user",)

    ordering = ("-created_at",)

    def content_object_display(self, obj):
        """
        Show human-readable target info in admin list view
        """
        if obj.content_object:
            return str(obj.content_object)
        return "Deleted Object"

    content_object_display.short_description = "Target Object"
