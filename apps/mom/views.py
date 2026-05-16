from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.utils.response import APIResponse
from .models import GeneralNote, Meeting, AgendaItem, MeetingNote
from .serializers import (
    GeneralNoteSerializer,
    MeetingListSerializer,
    MeetingCreateSerializer,
    MeetingUpdateSerializer,
    MeetingDetailSerializer,
    AgendaItemSerializer,
    MeetingNoteSerializer,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_meeting_or_error(user, meeting_id):
    try:
        return Meeting.objects.get(pk=meeting_id, user=user), None
    except Meeting.DoesNotExist:
        return None, APIResponse.error(message="Meeting not found", status_code=404)


def _all_meetings_agenda_stats(user):
    meetings = Meeting.objects.filter(user=user)
    total = AgendaItem.objects.filter(meeting__in=meetings).count()
    done = AgendaItem.objects.filter(meeting__in=meetings, is_done=True).count()
    percent = round((done / total) * 100) if total > 0 else 0
    return {"done": done, "total": total, "percent": percent}


# ---------------------------------------------------------------------------
# General Notes
# ---------------------------------------------------------------------------


class GeneralNoteListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notes = GeneralNote.objects.filter(user=request.user)
        serializer = GeneralNoteSerializer(notes, many=True)
        return APIResponse.success(data=serializer.data)

    def post(self, request):
        serializer = GeneralNoteSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        serializer.save(user=request.user)
        return APIResponse.success(
            data=serializer.data,
            message="Note created successfully",
            status_code=201,
        )


class GeneralNoteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_note(self, user, note_id):
        try:
            return GeneralNote.objects.get(pk=note_id, user=user), None
        except GeneralNote.DoesNotExist:
            return None, APIResponse.error(message="Note not found", status_code=404)

    def get(self, request, note_id):
        note, err = self._get_note(request.user, note_id)
        if err:
            return err
        return APIResponse.success(data=GeneralNoteSerializer(note).data)

    def patch(self, request, note_id):
        note, err = self._get_note(request.user, note_id)
        if err:
            return err
        serializer = GeneralNoteSerializer(note, data=request.data, partial=True)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        serializer.save()
        return APIResponse.success(
            data=serializer.data, message="Note updated successfully"
        )

    def delete(self, request, note_id):
        note, err = self._get_note(request.user, note_id)
        if err:
            return err
        note.delete()
        return APIResponse.success(message="Note deleted successfully")


# ---------------------------------------------------------------------------
# Meetings
# ---------------------------------------------------------------------------


class MeetingListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        meetings = Meeting.objects.filter(user=request.user).prefetch_related(
            "agenda_items"
        )
        serializer = MeetingListSerializer(meetings, many=True)
        return APIResponse.success(data=serializer.data)

    def post(self, request):
        serializer = MeetingCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        meeting = serializer.save(user=request.user)
        return APIResponse.success(
            data=MeetingDetailSerializer(meeting).data,
            message="Meeting created successfully",
            status_code=201,
        )


class MeetingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, meeting_id):
        meeting, err = _get_meeting_or_error(request.user, meeting_id)
        if err:
            return err
        return APIResponse.success(data=MeetingDetailSerializer(meeting).data)

    def patch(self, request, meeting_id):
        meeting, err = _get_meeting_or_error(request.user, meeting_id)
        if err:
            return err
        serializer = MeetingUpdateSerializer(meeting, data=request.data, partial=True)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        serializer.save()
        return APIResponse.success(
            data=MeetingDetailSerializer(meeting).data,
            message="Meeting updated successfully",
        )

    def delete(self, request, meeting_id):
        meeting, err = _get_meeting_or_error(request.user, meeting_id)
        if err:
            return err
        meeting.delete()
        return APIResponse.success(message="Meeting deleted successfully")


# ---------------------------------------------------------------------------
# Agenda Items
# ---------------------------------------------------------------------------


class AgendaItemListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, meeting_id):
        meeting, err = _get_meeting_or_error(request.user, meeting_id)
        if err:
            return err
        serializer = AgendaItemSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        serializer.save(meeting=meeting)
        return APIResponse.success(
            data=serializer.data,
            message="Agenda item added successfully",
            status_code=201,
        )


class AgendaItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_item(self, user, meeting_id, item_id):
        try:
            return (
                AgendaItem.objects.get(
                    pk=item_id, meeting__id=meeting_id, meeting__user=user
                ),
                None,
            )
        except AgendaItem.DoesNotExist:
            return None, APIResponse.error(
                message="Agenda item not found", status_code=404
            )

    def patch(self, request, meeting_id, item_id):
        """Toggle is_done or rename the agenda item."""
        item, err = self._get_item(request.user, meeting_id, item_id)
        if err:
            return err
        serializer = AgendaItemSerializer(item, data=request.data, partial=True)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        serializer.save()
        return APIResponse.success(
            data=serializer.data, message="Agenda item updated successfully"
        )

    def delete(self, request, meeting_id, item_id):
        item, err = self._get_item(request.user, meeting_id, item_id)
        if err:
            return err
        item.delete()
        return APIResponse.success(message="Agenda item deleted successfully")


# ---------------------------------------------------------------------------
# Meeting Notes (write-once)
# ---------------------------------------------------------------------------


class MeetingNoteListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, meeting_id):
        meeting, err = _get_meeting_or_error(request.user, meeting_id)
        if err:
            return err
        serializer = MeetingNoteSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        serializer.save(meeting=meeting)
        return APIResponse.success(
            data=serializer.data,
            message="Note added successfully",
            status_code=201,
        )


# ---------------------------------------------------------------------------
# Notes Tab — General notes + Meeting notes combined
# ---------------------------------------------------------------------------


class AllNotesListView(APIView):
    """
    Powers the 'Notes' tab. Returns general notes and meeting notes
    together in one sorted list so the frontend doesn't need two calls.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        general_notes = GeneralNote.objects.filter(user=request.user)
        meeting_notes = MeetingNote.objects.filter(
            meeting__user=request.user
        ).select_related("meeting")

        general_data = [
            {
                "id": note.id,
                "source": "general",
                "meeting_id": None,
                "meeting_title": None,
                "title": note.title,
                "description": note.description,
                "created_at": note.created_at,
            }
            for note in general_notes
        ]

        meeting_data = [
            {
                "id": note.id,
                "source": "meeting",
                "meeting_id": note.meeting.id,
                "meeting_title": note.meeting.title,
                "title": None,
                "description": note.description,
                "created_at": note.created_at,
            }
            for note in meeting_notes
        ]

        combined = sorted(
            general_data + meeting_data,
            key=lambda x: x["created_at"],
            reverse=True,
        )

        return APIResponse.success(data=combined)
