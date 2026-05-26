from django.contrib import admin
from .models import Like, Comment


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("user", "content_type", "object_id", "reaction", "created_at")
    list_filter = ("content_type", "reaction")
    search_fields = ("user__username", "user__name", "reaction", "object_id")
    readonly_fields = ("user", "content_type", "object_id", "created_at")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "content_type",
        "object_id",
        "parent",
        "is_deleted",
        "created_at",
    )

    list_filter = (
        "is_deleted",
        "content_type",
        "created_at",
    )

    search_fields = (
        "body",
        "user__username",
        "user__email",
        "object_id",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "content_type",
        "object_id",
        "parent",
        "user",
    )

    ordering = ("-created_at",)

    actions = ["soft_delete_comments", "restore_comments"]

    def soft_delete_comments(self, request, queryset):
        count = 0
        for comment in queryset:
            comment.soft_delete()
            count += 1
        self.message_user(request, f"{count} comments soft deleted.")

    soft_delete_comments.short_description = "Soft delete selected comments"

    def restore_comments(self, request, queryset):
        count = queryset.update(is_deleted=False, body="restored comment")
        self.message_user(request, f"{count} comments restored.")

    restore_comments.short_description = "Restore selected comments"
