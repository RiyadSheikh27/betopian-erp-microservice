from django.contrib import admin
from django.utils.html import format_html

from .models import Post, PostMedia, Reel

""" Inline for Post Media """


class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 1
    fields = (
        "media_preview",
        "file",
        "media_type",
        "caption",
        "order",
        "created_at",
    )
    readonly_fields = ("media_preview", "created_at")
    ordering = ("order",)

    def media_preview(self, obj):
        if obj.file:
            if obj.media_type == PostMedia.MediaType.IMAGE:
                return format_html(
                    '<img src="{}" width="80" height="80" style="object-fit:cover;border-radius:6px;" />',
                    obj.file.url,
                )
            return format_html(
                '<a href="{}" target="_blank">View Video</a>',
                obj.file.url,
            )
        return "-"

    media_preview.short_description = "Preview"


""" Post Admin """


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "author",
        "short_caption",
        "privacy",
        "media_count",
        "is_edited",
        "created_at",
    )

    list_filter = (
        "privacy",
        "is_edited",
        "created_at",
    )

    search_fields = (
        "author__username",
        "author__email",
        "caption",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    autocomplete_fields = ("author",)

    ordering = ("-created_at",)

    inlines = [PostMediaInline]

    fieldsets = (
        (
            "Post Information",
            {
                "fields": (
                    "author",
                    "caption",
                    "privacy",
                    "is_edited",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def short_caption(self, obj):
        return (
            obj.caption[:50] + "..."
            if obj.caption and len(obj.caption) > 50
            else obj.caption
        )

    short_caption.short_description = "Caption"

    def media_count(self, obj):
        return obj.media.count()

    media_count.short_description = "Media Count"


""" Post Media Admin """


@admin.register(PostMedia)
class PostMediaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "post",
        "media_type",
        "order",
        "media_preview",
        "created_at",
    )

    list_filter = (
        "media_type",
        "created_at",
    )

    search_fields = (
        "post__id",
        "post__author__username",
        "caption",
    )

    readonly_fields = (
        "media_preview",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = ("post",)

    ordering = ("post", "order")

    fieldsets = (
        (
            "Media Information",
            {
                "fields": (
                    "post",
                    "file",
                    "media_preview",
                    "media_type",
                    "caption",
                    "order",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def media_preview(self, obj):
        if obj.file:
            if obj.media_type == PostMedia.MediaType.IMAGE:
                return format_html(
                    '<img src="{}" width="100" height="100" style="object-fit:cover;border-radius:6px;" />',
                    obj.file.url,
                )
            return format_html(
                '<a href="{}" target="_blank">Open Video</a>',
                obj.file.url,
            )
        return "-"

    media_preview.short_description = "Preview"


""" Reel Admin """


@admin.register(Reel)
class ReelAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "author",
        "short_caption",
        "privacy",
        "view_count",
        "video_preview",
        "is_edited",
        "created_at",
    )

    list_filter = (
        "privacy",
        "is_edited",
        "created_at",
    )

    search_fields = (
        "author__username",
        "author__email",
        "caption",
    )

    readonly_fields = (
        "video_preview",
        "view_count",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = ("author",)

    ordering = ("-created_at",)

    fieldsets = (
        (
            "Reel Information",
            {
                "fields": (
                    "author",
                    "video",
                    "video_preview",
                    "caption",
                    "privacy",
                    "view_count",
                    "is_edited",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def short_caption(self, obj):
        return (
            obj.caption[:50] + "..."
            if obj.caption and len(obj.caption) > 50
            else obj.caption
        )

    short_caption.short_description = "Caption"

    def video_preview(self, obj):
        if obj.video:
            return format_html(
                '<video width="160" height="90" controls>'
                '<source src="{}" type="video/mp4">'
                "Your browser does not support the video tag."
                "</video>",
                obj.video.url,
            )
        return "-"

    video_preview.short_description = "Video Preview"
