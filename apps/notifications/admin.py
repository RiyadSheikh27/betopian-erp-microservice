from django.contrib import admin
from django.utils.html import format_html

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
    list_display = (
        "user_email",
        "user_name",
        "device_id",
        "platform",
        "token_preview",
        "voip_preview",
        "token_length",
        "updated_at",
    )
    list_filter = ("platform", "updated_at")
    search_fields = (
        "user__username",
        "user__email",
        "user__name",
        "device_id",
        "fcm_token",
        "voip_token",
    )
    readonly_fields = (
        "user",
        "device_id",
        "platform",
        "fcm_token",
        "voip_token",
        "token_preview",
        "voip_preview",
        "token_length",
        "created_at",
        "updated_at",
    )
    ordering = ("-updated_at",)
    date_hierarchy = "updated_at"
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    @admin.display(description="Email", ordering="user__email")
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description="Name", ordering="user__name")
    def user_name(self, obj):
        return obj.user.name

    @admin.display(description="FCM token (preview)")
    def token_preview(self, obj):
        if not obj.fcm_token:
            return format_html('<span style="color:#999;">empty</span>')
        preview = obj.fcm_token[:40] + ("…" if len(obj.fcm_token) > 40 else "")
        return format_html("<code>{}</code>", preview)

    @admin.display(description="VoIP token (preview)")
    def voip_preview(self, obj):
        if not obj.voip_token:
            return format_html('<span style="color:#999;">empty</span>')
        preview = obj.voip_token[:40] + ("…" if len(obj.voip_token) > 40 else "")
        return format_html("<code>{}</code>", preview)

    @admin.display(description="Token len", ordering="fcm_token")
    def token_length(self, obj):
        n = len(obj.fcm_token or "")
        if n == 0:
            return format_html('<span style="color:#c00;">0</span>')
        return n
