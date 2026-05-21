from django.db import models
from apps.utils.models import TimeStampedModel


class EbookTitle(TimeStampedModel):
    """A title/category that groups ebooks."""

    category_title = models.CharField(max_length=255, unique=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ["category_title"]

    def __str__(self):
        return self.category_title


class Ebook(TimeStampedModel):
    """An ebook PDF associated with a title."""

    category = models.ForeignKey(
        EbookTitle, on_delete=models.CASCADE, related_name="ebooks"
    )
    file_name = models.CharField(max_length=255)
    file = models.FileField(upload_to="ebooks/")

    class Meta(TimeStampedModel.Meta):
        db_table = "ebooks"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.category.category_title} — {self.file.name}"
