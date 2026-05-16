from django.db import models
from django.contrib.auth import get_user_model
from apps.utils.models import TimeStampedModel

User = get_user_model()


class GeneralNote(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="general_notes")
    title = models.CharField(max_length=255)
    description = models.TextField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Meeting(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="meetings")
    title = models.CharField(max_length=255)
    scheduled_at = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True, default="")
    participants = models.JSONField(default=list)

    class Meta:
        ordering = ["-scheduled_at"]

    def __str__(self):
        return self.title


class AgendaItem(TimeStampedModel):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="agenda_items")
    title = models.CharField(max_length=255)
    is_done = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title


class MeetingNote(TimeStampedModel):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="notes")
    description = models.TextField()

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Note for '{self.meeting.title}' at {self.created_at:%Y-%m-%d %H:%M}"