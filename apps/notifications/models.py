from django.conf import settings
from django.db import models

from apps.utils.models import TimeStampedModel


class Notification(TimeStampedModel):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event = models.CharField(max_length=30, db_index=True)
    payload = models.JSONField()
    is_read = models.BooleanField(default=False)

    class Meta(TimeStampedModel.Meta):
        db_table = "notifications"
        indexes = [
            models.Index(fields=["recipient", "-created_at"], name="idx_notif_recipient"),
        ]


class NotificationState(models.Model):
    """Tracks when the user last opened the notification list (badge count only)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="notification_state",
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_states"

class DeviceToken(models.Model):
    """Stores device tokens for push notifications."""
    
    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_tokens",
    )
    device_id = models.CharField(max_length=255)
    fcm_token = models.TextField(unique=True)
    platform = models.CharField(max_length=10, choices=Platform.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "device_tokens"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "device_id"],
                name="unique_user_device",
            )
        ]