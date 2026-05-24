import uuid
from django.db import models
from django.conf import settings
from django.db import models

""" Abstract base for every model in the project."""


class TimeStampedModel(models.Model):
    """UUID and timestamp fields for all models."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class ProfileImageStore(TimeStampedModel):
    """Stores profile images"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile_image"
    )
    profile_avatar = models.ImageField(upload_to="latest_profile_avatars/")

    class Meta(TimeStampedModel.Meta):
        db_table = "profile_image_store"

    def __str__(self):
        return f"Profile Image for {self.user.username} at {self.created_at}"

"""Dynamic Media Handling"""

class MediaHandling(models.Model):
    image_upload_max_size_mb = models.IntegerField(default=10)
    video_upload_max_size_mb = models.IntegerField(default=200)
    image_compression_quality = models.IntegerField(default=85)
    image_max_dimension = models.IntegerField(default=1920)
    avatar_max_dimension = models.IntegerField(default=400)

    def __str__(self):
        return "Media Handling Configuration"