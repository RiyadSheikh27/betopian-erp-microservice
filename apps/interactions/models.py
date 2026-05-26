from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.utils.models import TimeStampedModel

""" LIKE SECTION'S MODELS """


class Like(TimeStampedModel):
    """
    Unified reaction model for Post, PostMedia and Reel.
    reaction field stores which reaction the user chose.
    One row per user per target - switching reaction updates the row.
    Toggling the same reaction removes the row.
    """

    class Reaction(models.TextChoices):
        LOVE = "love", "Love"
        ANGRY = "angry", "Angry"
        HAHA = "haha", "Haha"
        WOW = "wow", "Wow"
        SAD = "sad", "Sad"
        CARE = "care", "Care"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")
    reaction = models.CharField(  
        max_length=10,
        choices=Reaction.choices,
        default=Reaction.LOVE,
    )

    class Meta(TimeStampedModel.Meta):
        db_table = "likes"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id"],
                name="unique_like_per_user_per_target",
            )
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id"], name="idx_like_target"),
            models.Index(
                fields=["user", "content_type", "object_id"],
                name="idx_like_user_target",
            ),
            # Fast filter by reaction type in reactor list
            models.Index(
                fields=["content_type", "object_id", "reaction"],
                name="idx_like_reaction",
            ), 
        ]


""" Comment Section """


class Comment(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    body = models.TextField()
    is_deleted = models.BooleanField(default=False)  # Soft Delete FloatRangeField

    class Meta(TimeStampedModel.Meta):
        db_table = "comments"
        indexes = [
            # Fast comment list per target
            models.Index(
                fields=["content_type", "object_id", "created_at"],
                name="idx_comment_target_created",
            ),
            # Fast reply list per parent
            models.Index(
                fields=["parent", "created_at"],
                name="idx_comment_parent_created",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} commented on {self.content_type} {self.object_id}"
