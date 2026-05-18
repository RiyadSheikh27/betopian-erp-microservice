import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.utils.response import APIResponse
from .models import Meeting, MeetingParticipant, AgendaItem, MeetingNote, GeneralNote
from .serializers import (
    GeneralNoteSerializer,
    AgendaItemSerializer,
    AgendaItemCreateSerializer,
    AgendaItemUpdateSerializer,
    MeetingNoteSerializer,
    MeetingListSerializer,
    MeetingDetailSerializer,
    MeetingCreateSerializer,
    MeetingUpdateSerializer,
    NotesTabSerializer,
)

logger = logging.getLogger("apps.mom")


def _central_id(request):
    """Extract central_id from the authenticated user."""
    return request.user.central_id


""" Views for Meeting and Notes (MoM) microservice. """


class GeneralNoteListCreateView(APIView):
    """List and create standalone general notes (not tied to any meeting)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        notes = GeneralNote.objects.filter(
            owner_central_id=_central_id(request)
        ).order_by("-created_at")
        return APIResponse.success(data=GeneralNoteSerializer(notes, many=True).data)

    def post(self, request):
        serializer = GeneralNoteSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        note = serializer.save(owner_central_id=_central_id(request))
        logger.info(
            "General note created | central_id=%s note_id=%s",
            _central_id(request),
            note.pk,
        )
        return APIResponse.success(
            data=GeneralNoteSerializer(note).data,
            message="Note created.",
            status_code=201,
        )


class GeneralNoteDetailView(APIView):
    """Retrieve, update or delete a general note. Only the owner can access their notes."""

    permission_classes = [IsAuthenticated]

    def _get_own(self, pk, request):
        try:
            return GeneralNote.objects.get(pk=pk, owner_central_id=_central_id(request))
        except GeneralNote.DoesNotExist:
            return None

    def get(self, request, pk):
        note = self._get_own(pk, request)
        if not note:
            return APIResponse.error(message="Note not found.", status_code=404)
        return APIResponse.success(data=GeneralNoteSerializer(note).data)

    def patch(self, request, pk):
        note = self._get_own(pk, request)
        if not note:
            return APIResponse.error(message="Note not found.", status_code=404)
        serializer = GeneralNoteSerializer(note, data=request.data, partial=True)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        serializer.save()
        logger.info(
            "General note updated | central_id=%s note_id=%s", _central_id(request), pk
        )
        return APIResponse.success(data=serializer.data, message="Note updated.")

    def delete(self, request, pk):
        note = self._get_own(pk, request)
        if not note:
            return APIResponse.error(message="Note not found.", status_code=404)
        note.delete()
        logger.info(
            "General note deleted | central_id=%s note_id=%s", _central_id(request), pk
        )
        return APIResponse.success(message="Note deleted.")


class MeetingListCreateView(APIView):
    """List all meetings for the user and create new meeting."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Returns all meetings where the user is a participant
        (includes meetings they created and meetings they were added to).
        """
        meeting_ids = MeetingParticipant.objects.filter(
            central_id=_central_id(request)
        ).values_list("meeting_id", flat=True)

        meetings = (
            Meeting.objects.filter(id__in=meeting_ids)
            .prefetch_related("participants", "agenda_items")
            .order_by("-created_at")
        )
        return APIResponse.success(data=MeetingListSerializer(meetings, many=True).data)

    def post(self, request):
        serializer = MeetingCreateSerializer(
            data=request.data,
            context={"central_id": _central_id(request)},
        )
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        meeting = serializer.save()
        logger.info(
            "Meeting created | central_id=%s meeting_id=%s",
            _central_id(request),
            meeting.pk,
        )
        return APIResponse.success(
            data=MeetingDetailSerializer(meeting, context={"request": request}).data,
            message="Meeting created.",
            status_code=201,
        )


class MeetingDetailView(APIView):
    """Retrieve, update or delete a meeting."""

    permission_classes = [IsAuthenticated]

    def _get_meeting_as_participant(self, pk, request):
        """Any participant can view the meeting."""
        try:
            meeting = Meeting.objects.prefetch_related(
                "participants", "agenda_items", "notes"
            ).get(pk=pk)
            # Verify requester is a participant
            if not meeting.participants.filter(
                central_id=_central_id(request)
            ).exists():
                return None, "not_participant"
            return meeting, None
        except Meeting.DoesNotExist:
            return None, "not_found"

    def _get_meeting_as_creator(self, pk, request):
        """Creator-only operations."""
        try:
            return (
                Meeting.objects.get(pk=pk, creator_central_id=_central_id(request)),
                None,
            )
        except Meeting.DoesNotExist:
            return None, "not_found"

    def get(self, request, pk):
        meeting, err = self._get_meeting_as_participant(pk, request)
        if err == "not_found":
            return APIResponse.error(message="Meeting not found.", status_code=404)
        if err == "not_participant":
            return APIResponse.error(
                message="You are not a participant of this meeting.", status_code=403
            )
        return APIResponse.success(
            data=MeetingDetailSerializer(meeting, context={"request": request}).data
        )

    def patch(self, request, pk):
        """Creator only."""
        meeting, _ = self._get_meeting_as_creator(pk, request)
        if not meeting:
            return APIResponse.error(
                message="Meeting not found or you are not the creator.", status_code=404
            )
        serializer = MeetingUpdateSerializer(
            meeting,
            data=request.data,
            partial=True,
            context={"central_id": _central_id(request)},
        )
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        updated = serializer.save()
        logger.info(
            "Meeting updated | central_id=%s meeting_id=%s", _central_id(request), pk
        )
        return APIResponse.success(
            data=MeetingDetailSerializer(updated, context={"request": request}).data,
            message="Meeting updated.",
        )

    def delete(self, request, pk):
        """
        Creator - hard deletes meeting and everything under it.
        Participant - removes only themselves from participant list.
        """
        cid = _central_id(request)

        # Check if creator
        try:
            meeting = Meeting.objects.get(pk=pk, creator_central_id=cid)
            meeting.delete()  # cascades agenda, notes, participants
            logger.info(
                "Meeting deleted by creator | central_id=%s meeting_id=%s", cid, pk
            )
            return APIResponse.success(message="Meeting deleted.")
        except Meeting.DoesNotExist:
            pass

        # Check if participant
        deleted, _ = MeetingParticipant.objects.filter(
            meeting_id=pk, central_id=cid
        ).delete()

        if deleted:
            logger.info(
                "Participant left meeting | central_id=%s meeting_id=%s", cid, pk
            )
            return APIResponse.success(message="Removed from meeting.")

        return APIResponse.error(message="Meeting not found.", status_code=404)


class AgendaItemCreateView(APIView):
    """Creator only - add agenda item to a meeting."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            meeting = Meeting.objects.get(
                pk=pk, creator_central_id=_central_id(request)
            )
        except Meeting.DoesNotExist:
            return APIResponse.error(
                message="Meeting not found or you are not the creator.", status_code=404
            )

        serializer = AgendaItemCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)

        item = serializer.save(meeting=meeting)
        logger.info(
            "Agenda item added | central_id=%s meeting_id=%s item_id=%s",
            _central_id(request),
            pk,
            item.pk,
        )
        return APIResponse.success(
            data=AgendaItemSerializer(item).data,
            message="Agenda item added.",
            status_code=201,
        )


class AgendaItemDetailView(APIView):
    """Creator only - update or delete agenda item."""

    permission_classes = [IsAuthenticated]

    def _get_item(self, pk, item_id, request):
        try:
            return AgendaItem.objects.get(
                pk=item_id,
                meeting_id=pk,
                meeting__creator_central_id=_central_id(request),
            )
        except AgendaItem.DoesNotExist:
            return None

    def patch(self, request, pk, item_id):
        item = self._get_item(pk, item_id, request)
        if not item:
            return APIResponse.error(message="Agenda item not found.", status_code=404)
        serializer = AgendaItemUpdateSerializer(item, data=request.data, partial=True)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        serializer.save()
        logger.info(
            "Agenda item updated | central_id=%s item_id=%s",
            _central_id(request),
            item_id,
        )
        return APIResponse.success(
            data=AgendaItemSerializer(item).data, message="Agenda item updated."
        )

    def delete(self, request, pk, item_id):
        item = self._get_item(pk, item_id, request)
        if not item:
            return APIResponse.error(message="Agenda item not found.", status_code=404)
        item.delete()
        logger.info(
            "Agenda item deleted | central_id=%s item_id=%s",
            _central_id(request),
            item_id,
        )
        return APIResponse.success(message="Agenda item deleted.")


class MeetingNoteCreateView(APIView):
    """Any participant can add a note. Write-once - no edit or delete."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        # Verify requester is a participant
        is_participant = MeetingParticipant.objects.filter(
            meeting_id=pk, central_id=_central_id(request)
        ).exists()
        if not is_participant:
            return APIResponse.error(message="Meeting not found.", status_code=404)

        serializer = MeetingNoteSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)

        note = serializer.save(
            meeting_id=pk, created_by_central_id=_central_id(request)
        )
        logger.info(
            "Meeting note added | central_id=%s meeting_id=%s note_id=%s",
            _central_id(request),
            pk,
            note.pk,
        )
        return APIResponse.success(
            data=MeetingNoteSerializer(note).data,
            message="Note added.",
            status_code=201,
        )


class MeetingNoteDetailView(APIView):
    """Owner only - edit or delete own meeting note."""

    permission_classes = [IsAuthenticated]

    def _get_own_note(self, note_id, request):
        try:
            return MeetingNote.objects.get(
                pk=note_id,
                created_by_central_id=_central_id(request),
            )
        except MeetingNote.DoesNotExist:
            return None

    def patch(self, request, pk, note_id):
        note = self._get_own_note(note_id, request)
        if not note:
            return APIResponse.error(message="Note not found.", status_code=404)
        serializer = MeetingNoteSerializer(note, data=request.data, partial=True)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        serializer.save()
        logger.info(
            "Meeting note updated | central_id=%s note_id=%s",
            _central_id(request),
            note_id,
        )
        return APIResponse.success(
            data=MeetingNoteSerializer(note).data, message="Note updated."
        )

    def delete(self, request, pk, note_id):
        note = self._get_own_note(note_id, request)
        if not note:
            return APIResponse.error(message="Note not found.", status_code=404)
        note.delete()
        logger.info(
            "Meeting note deleted | central_id=%s note_id=%s",
            _central_id(request),
            note_id,
        )
        return APIResponse.success(message="Note deleted.")


class NotesTabView(APIView):
    """
    Merges general notes and meeting notes into one list, newest first.
    Powers the Notes tab in the app.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        cid = _central_id(request)

        general_notes = GeneralNote.objects.filter(owner_central_id=cid)
        meeting_notes = MeetingNote.objects.filter(
            meeting__participants__central_id=cid
        ).select_related("meeting")

        unified = []

        for n in general_notes:
            unified.append(
                {
                    "id": n.id,
                    "source": "general",
                    "meeting_id": None,
                    "meeting_title": None,
                    "title": n.title,
                    "description": n.description,
                    "created_at": n.created_at,
                }
            )

        for n in meeting_notes:
            unified.append(
                {
                    "id": n.id,
                    "source": "meeting",
                    "meeting_id": n.meeting.id,
                    "meeting_title": n.meeting.title,
                    "title": None,
                    "description": n.description,
                    "created_at": n.created_at,
                }
            )

        unified.sort(key=lambda x: x["created_at"], reverse=True)

        return APIResponse.success(data=NotesTabSerializer(unified, many=True).data)
