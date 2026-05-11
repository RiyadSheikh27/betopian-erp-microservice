from django.conf import settings
from django.db import models
from apps.utils.models import TimeStampedModel

""" Post Manage Section """


class Post(TimeStampedModel):
    """User post - text caption with optional media attachments."""

    class Privacy(models.TextChoices):
        PUBLIC = "public", "Public"
        ONLY_ME = "only_me", "Only Me"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    caption = models.TextField(blank=True)
    privacy = models.CharField(
        max_length=10,
        choices=Privacy.choices,
        default=Privacy.PUBLIC,
    )
    is_edited = models.BooleanField(default=False)

    class Meta(TimeStampedModel.Meta):
        db_table = "posts"
        indexes = [
            # filter by author - order by created_at + id in one scan.
            models.Index(
                fields=["author", "-created_at", "-id"], name="idx_post_author_created"
            ),
        ]

    def __str__(self):
        return f"Post {self.pk} by {self.author.username}"


class PostMedia(TimeStampedModel):
    """Image or Video attached to a post"""

    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="media")
    file = models.FileField(upload_to="posts/%Y/%m/%d/")
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    caption = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta(TimeStampedModel.Meta):
        db_table = "Post_media"
        ordering = ["order"]

    def __str__(self):
        return f"{self.media_type} for post {self.post.id}"


class Reel(TimeStampedModel):
    """Reels - single video + caption)."""

    class Privacy(models.TextChoices):
        PUBLIC = "public", "Public"
        ONLY_ME = "only_me", "Only Me"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reels",
    )
    video = models.FileField(upload_to="reels/%Y/%m/%d/")
    caption = models.TextField(blank=True)
    privacy = models.CharField(
        max_length=10, choices=Privacy.choices, default=Privacy.PUBLIC
    )
    view_count = models.PositiveBigIntegerField(default=0)
    is_edited = models.BooleanField(default=False)

    class Meta(TimeStampedModel.Meta):
        db_table = "reels"
        indexes = [
            models.Index(fields=["-created_at", "-id"], name="idx_reel_created"),
            models.Index(
                fields=["author", "-created_at", "-id"], name="idx_reel_author_created"
            ),
        ]

    def __str__(self):
        return f"Reel {self.pk} by {self.author.username}"
