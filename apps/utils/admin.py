from django.contrib import admin
from .models import MediaHandling


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
