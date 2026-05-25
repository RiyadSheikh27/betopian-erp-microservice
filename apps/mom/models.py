from django.db import models
from apps.utils.models import TimeStampedModel


class Meeting(TimeStampedModel):
    """A scheduled meeting created by a central-system user."""

    creator_central_id = models.BigIntegerField(db_index=True)
    title = models.CharField(max_length=255)
    scheduled_at = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True)

    class Meta(TimeStampedModel.Meta):
        db_table = "mom_meetings"
        indexes = [
            models.Index(
                fields=["creator_central_id", "created_at"],
                name="idx_meeting_creator",
            ),
        ]

    def __str__(self):
        return f"{self.title} (creator={self.creator_central_id})"


class MeetingPin(TimeStampedModel):
    """Tracks which meetings a user has pinned."""

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="pins")
    central_id = models.BigIntegerField(db_index=True)

    class Meta(TimeStampedModel.Meta):
        db_table = "mom_meeting_pins"
        constraints = [
            models.UniqueConstraint(
                fields=["meeting", "central_id"],
                name="unique_pin_per_user_per_meeting",
            ),
        ]

    def __str__(self):
        return f"Pin(meeting={self.meeting_id}, user={self.central_id})"


class MeetingParticipant(TimeStampedModel):
    """
    A participant in a meeting, identified by their central-system primary key.

    Profile fields (employee_id, username, avatar_url, designation) are cached
    locally to avoid hitting the central API on every list request.  They are
    backfilled/refreshed lazily whenever a bulk profile fetch is performed.
    """

    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="participants"
    )
    # The primary key used by the central ERP / employee-directory service.
    central_id = models.BigIntegerField(db_index=True)

    # Cached profile fields (populated from employee-directory API) ---
    # The central directory uses `employee_code` as the key in its API.
    # The DB currently contains `employee_code`, so we store that field
    # and provide a backward-compatible `employee_id` property used
    # elsewhere in the codebase.
    employee_code = models.CharField(max_length=50, blank=True)
    username = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(max_length=10_000, blank=True)
    designation = models.CharField(max_length=255, blank=True)

    is_creator = models.BooleanField(default=False)

    class Meta(TimeStampedModel.Meta):
        db_table = "mom_meeting_participants"
        constraints = [
            models.UniqueConstraint(
                fields=["meeting", "central_id"],
                name="unique_participant_per_meeting",
            ),
        ]
        indexes = [
            models.Index(
                fields=["central_id", "created_at"],
                name="idx_participant_user",
            ),
        ]

    def __str__(self):
        return f"{self.username or self.central_id} in '{self.meeting.title}'"

    @property
    def employee_id(self):
        return self.employee_code

    @employee_id.setter
    def employee_id(self, value):
        self.employee_code = value


class AgendaItem(TimeStampedModel):
    """A single agenda item belonging to a meeting."""

    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="agenda_items"
    )
    title = models.CharField(max_length=255)
    is_done = models.BooleanField(default=False)

    class Meta(TimeStampedModel.Meta):
        db_table = "mom_agenda_items"
        ordering = ["created_at"]

    def __str__(self):
        status = "done" if self.is_done else "pending"
        return f"{self.title} ({status})"


class MeetingNote(TimeStampedModel):
    """A note written by a participant during or after a meeting."""

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="notes")
    description = models.TextField()
    created_by_central_id = models.BigIntegerField(db_index=True)
    is_pinned = models.BooleanField(default=False)

    class Meta(TimeStampedModel.Meta):
        db_table = "mom_meeting_notes"
        ordering = ["created_at"]

    def __str__(self):
        return f"Note for '{self.meeting.title}' by {self.created_by_central_id}"


class GeneralNote(TimeStampedModel):
    """A personal note that is not tied to any specific meeting."""

    owner_central_id = models.BigIntegerField(db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    is_pinned = models.BooleanField(default=False)

    class Meta(TimeStampedModel.Meta):
        db_table = "mom_general_notes"
        indexes = [
            models.Index(
                fields=["owner_central_id", "created_at"],
                name="idx_note_owner",
            ),
        ]

    def __str__(self):
        return f"{self.title} (owner={self.owner_central_id})"
