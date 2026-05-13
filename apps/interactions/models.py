from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.utils.models import TimeStampedModel


class Like(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta(TimeStampedModel.Meta):
        db_table = "likes"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id"],
                name="unique_like_per_user_per_object",
            )
        ]
        indexes = [
            models.Index(
                fields=["content_type", "object_id"],
                name="idx_like_target",
            ),
            # Fast check - has this user liked this target?
            models.Index(
                fields=["user", "content_type", "object_id"],
                name="idx_like_user_target",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} liked {self.content_type} {self.object_id}"
