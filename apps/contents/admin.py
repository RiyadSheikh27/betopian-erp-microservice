from django.contrib import admin
from .models import Post, PostMedia


class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 0
    readonly_fields = ("media_type", "order")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "author",
        "caption_preview",
        "media_count",
        "is_edited",
        "created_at",
    )
    list_filter = ("is_edited", "created_at")
    search_fields = ("author__username", "caption")
    readonly_fields = ("is_edited", "created_at", "updated_at")
    inlines = [PostMediaInline]

    def caption_preview(self, obj):
        return obj.caption[:60] + "..." if len(obj.caption) > 60 else obj.caption

    caption_preview.short_description = "Caption"

    def media_count(self, obj):
        return obj.media.count()

    media_count.short_description = "Media"
