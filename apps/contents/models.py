from django.conf import settings
from django.db import models
from apps.utils.models import TimeStampedModel
from django.contrib.contenttypes.fields import GenericRelation

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

""" Community Section """


class Community(TimeStampedModel):
    """Community model for group posting and interactions."""

    class CommunityType(models.TextChoices):
        LOCATION = "location", "Location"
        COMPANY = "company", "Company"
        DEPARTMENT = "department", "Department"

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(
        upload_to="community_covers/", blank=True, null=True
    )
    type = models.CharField(max_length=20, choices=CommunityType.choices)
    keywords = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta(TimeStampedModel.Meta):
        db_table = "communities"
        indexes = [
            models.Index(fields=["type"], name="idx_community_type"),
        ]

    def __str__(self):
        return f"{self.name} ({self.type})"


class CommunityMember(TimeStampedModel):
    """Membership model linking users to communities with roles."""

    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_memberships",
    )
    role = models.CharField(max_length=50, default="member")

    class Meta(TimeStampedModel.Meta):
        db_table = "community_members"
        constraints = [
            models.UniqueConstraint(
                fields=["community", "user"], name="unique_community_member"
            )
        ]
        indexes = [
            models.Index(
                fields=["user", "created_at"], name="idx_community_member_user"
            ),
        ]

    def __str__(self):
        return f"{self.user.username} in {self.community.name} as {self.role}"


""" Content Manage Section """


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
    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, related_name="posts", blank=True, null=True
    )
    caption = models.TextField(blank=True)
    privacy = models.CharField(
        max_length=10,
        choices=Privacy.choices,
        default=Privacy.PUBLIC,
    )
    likes = GenericRelation("interactions.Like", related_query_name="post")
    comments = GenericRelation("interactions.Comment", related_query_name="post")
    is_edited = models.BooleanField(default=False)

    class Meta(TimeStampedModel.Meta):
        db_table = "posts"
        indexes = [
            models.Index(
                fields=["author", "-created_at", "-id"], name="idx_post_author_created"
            ),
            models.Index(fields=["-created_at", "-id"], name="idx_post_created"),
            models.Index(
                fields=["community", "-created_at"], name="idx_post_community"
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
    likes = GenericRelation("interactions.Like")
    comments = GenericRelation("interactions.Comment")
    view_count = models.PositiveBigIntegerField(default=0)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta(TimeStampedModel.Meta):
        db_table = "Post_media"
        ordering = ["order"]
        indexes = [
            models.Index(
                fields=["media_type", "-created_at"],
                name="idx_postmedia_type_created",
            ),
        ]

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
    likes = GenericRelation("interactions.Like")
    comments = GenericRelation("interactions.Comment")
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


class ReelView(TimeStampedModel):
    """Count of view in Reel Section"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reel_views"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")
    view_count = models.PositiveSmallIntegerField(default=1)

    class Meta(TimeStampedModel.Meta):
        db_table = "reel_views"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id"],
                name="unique_reel_view_per_user",
            )
        ]
        indexes = [
            models.Index(
                fields=["content_type", "object_id"],
                name="idx_reelview_target",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} viewed {self.object_id} x{self.view_count}"


class SavedItem(TimeStampedModel):
    """Save any post or reel for latter viewing"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_items",
    )
    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.CASCADE
    )
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta(TimeStampedModel.Meta):
        db_table = "saved_items"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id"],
                name="unique_saved_item_per_user",
            )
        ]
        indexes = [
            models.Index(
                fields=["user", "-created_at"],
                name="idx_saved_user_created",
            ),
        ]
        
    def __str__(self):
        return f"{self.user.username} saved {self.content_type} {self.object_id}"