from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils import timezone

from apps.utils.models import TimeStampedModel


class Story(TimeStampedModel):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stories",
    )
    file = models.FileField(upload_to="stories/%Y/%m/%d/")
    thumbnail = models.ImageField(
        upload_to="stories/thumbnails/%Y/%m/%d/",
        blank=True,
        null=True,
    )
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    expires_at = models.DateTimeField(db_index=True)
    likes = GenericRelation("interactions.Like")

    class Meta(TimeStampedModel.Meta):
        db_table = "stories"
        indexes = [
            models.Index(
                fields=["author", "-created_at"],
                name="idx_story_author_created",
            ),
            models.Index(
                fields=["expires_at", "author"],
                name="idx_story_expires_author",
            ),
        ]

    def __str__(self):
        return f"Story {self.pk} by {self.author_id}"

    @property
    def is_active(self):
        return self.expires_at > timezone.now()

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)


class StoryView(TimeStampedModel):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="views")
    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="story_views",
    )
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta(TimeStampedModel.Meta):
        db_table = "story_views"
        constraints = [
            models.UniqueConstraint(
                fields=["story", "viewer"],
                name="unique_story_view",
            )
        ]
        indexes = [
            models.Index(fields=["story", "-viewed_at"], name="idx_storyview_story"),
        ]


class StoryTrayState(TimeStampedModel):
    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="story_tray_states",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="story_tray_seen_by",
    )
    last_viewed_at = models.DateTimeField(auto_now=True)

    class Meta(TimeStampedModel.Meta):
        db_table = "story_tray_states"
        constraints = [
            models.UniqueConstraint(
                fields=["viewer", "author"],
                name="unique_story_tray_state",
            )
        ]
