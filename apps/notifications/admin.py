from django.contrib import admin

from .models import DeviceToken, Notification, NotificationState


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


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "device_id", "platform", "created_at", "updated_at")
    list_filter = ("platform", "created_at")
    search_fields = ("user__username", "user__email", "device_id", "fcm_token")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-updated_at",)
