from django.contrib import admin
from .models import MediaHandling, ProfileImageStore


@admin.register(ProfileImageStore)
class ProfileImageStoreAdmin(admin.ModelAdmin):
    list_display = ("user", "profile_avatar", "created_at", "updated_at")
    search_fields = ("user__username", "user__email", "user__name")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(MediaHandling)
class MediaHandlingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "image_upload_max_size_mb",
        "video_upload_max_size_mb",
        "image_compression_quality",
        "image_max_dimension",
        "avatar_max_dimension",
    )

    fieldsets = (
        (
            "Upload Limits",
            {
                "fields": (
                    "image_upload_max_size_mb",
                    "video_upload_max_size_mb",
                )
            },
        ),
        (
            "Image Processing",
            {
                "fields": (
                    "image_compression_quality",
                    "image_max_dimension",
                    "avatar_max_dimension",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        # optional: allow only ONE config row
        if MediaHandling.objects.exists():
            return False
        return True
