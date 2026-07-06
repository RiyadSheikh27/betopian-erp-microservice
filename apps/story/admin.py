from django.contrib import admin

from .models import Story, StoryTrayState, StoryView


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "media_type", "expires_at", "created_at")
    list_filter = ("media_type", "created_at")
    search_fields = ("author__email", "author__name")
    readonly_fields = ("created_at", "updated_at")


admin.site.register(StoryView)
admin.site.register(StoryTrayState)
