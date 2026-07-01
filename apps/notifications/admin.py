from django.contrib import admin

from .models import Notification, NotificationState


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "event", "is_read", "created_at")
    list_filter = ("event", "is_read")
    search_fields = ("recipient__username", "recipient__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(NotificationState)
class NotificationStateAdmin(admin.ModelAdmin):
    list_display = ("user", "last_seen_at", "updated_at")
    search_fields = ("user__username", "user__email")
