from django.db import models
from apps.utils.models import TimeStampedModel


class Meeting(TimeStampedModel):
    """
    A meeting created by a central ERP user.
    creator_central_id — central user ID of who created the meeting.
    No FK to local User model — MOM is auth-independent from social media.
    """

    creator_central_id = models.BigIntegerField(db_index=True)
    title = models.CharField(max_length=255)
    scheduled_at = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True)

    class Meta(TimeStampedModel.Meta):
        db_table = "mom_meetings"
        indexes = [
            models.Index(
                fields=["creator_central_id", "-created_at"], name="idx_meeting_creator"
            ),
        ]

    def __str__(self):
        return f"{self.title} by {self.creator_central_id}"


class MeetingParticipant(TimeStampedModel):
    """
    Links a central user to a meeting.
    - Creator is also added as a participant on meeting creation.
    - Participant can remove themselves (soft via is_active=False).
    - Creator delete cascades — hard deletes the meeting and all participants.
    """

    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="participants"
    )
    central_id = models.BigIntegerField(db_index=True)
    is_creator = models.BooleanField(default=False)

    class Meta(TimeStampedModel.Meta):
        db_table = "mom_meeting_participants"
        constraints = [
            models.UniqueConstraint(
                fields=["meeting", "central_id"],
                name="unique_participant_per_meeting",
            )
        ]
        indexes = [
            # Fast lookup — all meetings for a specific user
            models.Index(
                fields=["central_id", "-created_at"], name="idx_participant_user"
            ),
        ]

    def __str__(self):
        return f"central_id={self.central_id} in {self.meeting.title}"


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
        return f"{self.title} ({'done' if self.is_done else 'pending'})"


class MeetingNote(TimeStampedModel):
    """
    Write-once notes attached to a meeting.
    No edit or delete — intentional audit trail.
    """

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="notes")
    description = models.TextField()
    created_by_central_id = models.BigIntegerField(db_index=True) 

    class Meta(TimeStampedModel.Meta):
        db_table = "mom_meeting_notes"
        ordering = ["created_at"]

    def __str__(self):
        return f"Note for {self.meeting.title}"


class GeneralNote(TimeStampedModel):
    """Standalone note — not tied to any meeting."""

    owner_central_id = models.BigIntegerField(db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField()

    class Meta(TimeStampedModel.Meta):
        db_table = "mom_general_notes"
        indexes = [
            models.Index(
                fields=["owner_central_id", "-created_at"], name="idx_note_owner"
            ),
        ]

    def __str__(self):
        return f"{self.title} by {self.owner_central_id}"

