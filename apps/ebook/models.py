from django.db import models
from apps.utils.models import TimeStampedModel


class EbookTitle(TimeStampedModel):
    """A title/category that groups ebooks."""

    ebook_title = models.CharField(max_length=255, unique=True)

    class Meta(TimeStampedModel.Meta):
        db_table = "ebook_titles"
        ordering = ["ebook_title"]

    def __str__(self):
        return self.ebook_title


class Ebook(TimeStampedModel):
    """An ebook PDF associated with a title."""

    title = models.ForeignKey(
        EbookTitle, on_delete=models.CASCADE, related_name="ebooks"
    )
    file = models.FileField(upload_to="ebooks/")

    class Meta(TimeStampedModel.Meta):
        db_table = "ebooks"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title.ebook_title} — {self.file.name}"
