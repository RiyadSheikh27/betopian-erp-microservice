from django.contrib import admin
from .models import Community, CommunityMember, Post, PostMedia, Reel, ReelView

""" Inline for Post Media """


class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 0
    fields = ("file", "media_type", "caption", "order", "view_count")
    readonly_fields = ("view_count",)


""" Community Admin """


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "type", "is_active", "created_at")
    list_filter = ("type", "is_active", "created_at")
    search_fields = ("name", "description", "keywords")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


""" Community Member Admin """


@admin.register(CommunityMember)
class CommunityMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "community", "role", "created_at")
    list_filter = ("role", "community")
    search_fields = ("user__username", "community__name")
    autocomplete_fields = ("user", "community")
    ordering = ("-created_at",)


""" Post Admin """


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "author",
        "community",
        "privacy",
        "is_edited",
        "created_at",
    )
    list_filter = ("privacy", "community", "is_edited", "created_at")
    search_fields = ("caption", "author__username", "community__name")
    autocomplete_fields = ("author", "community")
    inlines = [PostMediaInline]
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


""" Post Media Admin """


@admin.register(PostMedia)
class PostMediaAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "media_type", "order", "view_count", "created_at")
    list_filter = ("media_type", "created_at")
    search_fields = ("post__caption",)
    autocomplete_fields = ("post",)
    ordering = ("post", "order")


""" Reel Admin """


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
    list_filter = ("privacy", "created_at", "is_edited")
    search_fields = ("caption", "author__username")
    autocomplete_fields = ("author",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")

@admin.register(ReelView)
class ReelViewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "content_type",
        "object_id",
        "view_count",
        "created_at",
    )

    list_filter = (
        "content_type",
        "created_at",
    )

    search_fields = (
        "user__username",
        "object_id",
    )

    autocomplete_fields = ("user",)

    ordering = ("-created_at",)

    readonly_fields = (
        "created_at",
        "updated_at",
    )