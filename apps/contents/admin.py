from django.contrib import admin
from .models import Post, PostMedia, Reel


class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 1
    fields = (
        "file",
        "media_type",
        "caption",
        "view_count",
        "order",
    )
    readonly_fields = ("view_count",)
    ordering = ("order",)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "author",
        "privacy",
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
        "caption",
    )
    ordering = ("-created_at",)
    readonly_fields = (
        "created_at",
        "updated_at",
    )
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
                )
            },
        ),
    )


@admin.register(PostMedia)
class PostMediaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "post",
        "media_type",
        "view_count",
        "order",
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
    ordering = ("post", "order")
    readonly_fields = (
        "view_count",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Media Information",
            {
                "fields": (
                    "post",
                    "file",
                    "media_type",
                    "caption",
                    "order",
                    "view_count",
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


@admin.register(Reel)
class ReelAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "author",
        "privacy",
        "view_count",
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
        "caption",
    )
    ordering = ("-created_at",)
    readonly_fields = (
        "view_count",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Reel Information",
            {
                "fields": (
                    "author",
                    "video",
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
                )
            },
        ),
    )
