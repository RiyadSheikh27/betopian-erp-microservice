import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Story",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("file", models.FileField(upload_to="stories/%Y/%m/%d/")),
                (
                    "thumbnail",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="stories/thumbnails/%Y/%m/%d/",
                    ),
                ),
                (
                    "media_type",
                    models.CharField(
                        choices=[("image", "Image"), ("video", "Video")],
                        max_length=10,
                    ),
                ),
                ("expires_at", models.DateTimeField(db_index=True)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stories",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "stories",
                "ordering": ["-created_at"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="StoryTrayState",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_viewed_at", models.DateTimeField(auto_now=True)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="story_tray_seen_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "viewer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="story_tray_states",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "story_tray_states",
                "ordering": ["-created_at"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="StoryView",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("viewed_at", models.DateTimeField(auto_now=True)),
                (
                    "story",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="views",
                        to="story.story",
                    ),
                ),
                (
                    "viewer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="story_views",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "story_views",
                "ordering": ["-created_at"],
                "abstract": False,
            },
        ),
        migrations.AddIndex(
            model_name="story",
            index=models.Index(
                fields=["author", "-created_at"], name="idx_story_author_created"
            ),
        ),
        migrations.AddIndex(
            model_name="story",
            index=models.Index(
                fields=["expires_at", "author"], name="idx_story_expires_author"
            ),
        ),
        migrations.AddConstraint(
            model_name="storytraystate",
            constraint=models.UniqueConstraint(
                fields=("viewer", "author"), name="unique_story_tray_state"
            ),
        ),
        migrations.AddIndex(
            model_name="storyview",
            index=models.Index(
                fields=["story", "-viewed_at"], name="idx_storyview_story"
            ),
        ),
        migrations.AddConstraint(
            model_name="storyview",
            constraint=models.UniqueConstraint(
                fields=("story", "viewer"), name="unique_story_view"
            ),
        ),
    ]
