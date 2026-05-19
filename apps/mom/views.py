import logging

from django.db import models as django_models
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.authentication.backends import fetch_central_profiles_bulk
from apps.utils.response import APIResponse

from .models import (
    Meeting,
    MeetingPin,
    MeetingParticipant,
    AgendaItem,
    MeetingNote,
    GeneralNote,
)
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


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _central_id(request):
    """Return the authenticated user's central-system primary key."""
    return request.user.central_id


def _credentials(request):
    """Return (token, session_id) for central API calls."""
    token = getattr(request.user, "central_access_token", "")
    session_id = request.COOKIES.get("session_id", "")
    return token, session_id


def _profile_to_participant_fields(profile: dict) -> dict:
    """
    Map an employee-directory API response to ``MeetingParticipant`` model fields.

    The employee-directory returns keys: id, employee_code, name, job_title,
    department, work_email, avatar_url, …
    """
    if not profile:
        return {}
    return {
        "employee_id": profile.get("employee_code", ""),
        "username": profile.get("name", ""),
        "avatar_url": profile.get("avatar_url", ""),
        "designation": profile.get("job_title") or profile.get("department", ""),
    }


def _backfill_stale_participants(meetings, all_profiles: dict):
    """
    When a participant row has no cached username (e.g. the central API was
    unavailable at creation time), write fresh profile data back to the DB.
    This keeps the local cache up-to-date without a dedicated sync job.
    """
    to_update = []
    for meeting in meetings:
        for participant in meeting.participants.all():
            if participant.username:
                continue
            profile = all_profiles.get(participant.central_id)
            if not profile:
                continue
            fields = _profile_to_participant_fields(profile)
            participant.username = fields.get("username", "")
            participant.employee_id = fields.get("employee_id", "")
            participant.avatar_url = fields.get("avatar_url", "")
            participant.designation = fields.get("designation", "")
            to_update.append(participant)

    if to_update:
        MeetingParticipant.objects.bulk_update(
            to_update, ["username", "employee_id", "avatar_url", "designation"]
        )
        logger.info("Backfilled %d stale participant record(s).", len(to_update))


def _build_meeting_context(request, meetings):
    """
    Fetch live profiles for all participants across *meetings* and return the
    serializer context dict.

    Passing the full profile map to the serializer means we only hit the
    central API once per request, regardless of how many meetings are listed.
    """
    cid = _central_id(request)
    token, session_id = _credentials(request)

    all_central_ids = list(
        {p.central_id for m in meetings for p in m.participants.all()}
    )
    all_profiles = fetch_central_profiles_bulk(all_central_ids, token, session_id)
    _backfill_stale_participants(meetings, all_profiles)

    pinned_ids = set(
        MeetingPin.objects.filter(
            central_id=cid,
            meeting_id__in=[m.id for m in meetings],
        ).values_list("meeting_id", flat=True)
    )

    participant_profiles = {
        str(m.id): {
            p.central_id: all_profiles.get(p.central_id) for p in m.participants.all()
        }
        for m in meetings
    }

    return {
        "request": request,
        "participant_profiles": participant_profiles,
        "pinned_meeting_ids": pinned_ids,
    }


# ---------------------------------------------------------------------------
# General Notes
# ---------------------------------------------------------------------------


class GeneralNoteListCreateView(APIView):
    """
    GET  /notes/    – list all personal notes for the authenticated user.
    POST /notes/    – create a new personal note.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = GeneralNote.objects.filter(owner_central_id=_central_id(request))
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                django_models.Q(title__icontains=search)
                | django_models.Q(description__icontains=search)
            )
        qs = qs.order_by("-is_pinned", "-created_at")
        return APIResponse.success(data=GeneralNoteSerializer(qs, many=True).data)

    def post(self, request):
        serializer = GeneralNoteSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        note = serializer.save(owner_central_id=_central_id(request))
        logger.info(
            "Note created | central_id=%s note_id=%s", _central_id(request), note.pk
        )
        return APIResponse.success(
            data=GeneralNoteSerializer(note).data,
            message="Note created.",
            status_code=201,
        )


class GeneralNoteDetailView(APIView):
    """
    GET    /notes/<pk>/  – retrieve a personal note.
    PATCH  /notes/<pk>/  – partial update.
    DELETE /notes/<pk>/  – delete.
    """

    permission_classes = [IsAuthenticated]

    def _get_note_or_404(self, pk, request):
        try:
            return GeneralNote.objects.get(pk=pk, owner_central_id=_central_id(request))
        except GeneralNote.DoesNotExist:
            return None

    def get(self, request, pk):
        note = self._get_note_or_404(pk, request)
        if not note:
            return APIResponse.error(message="Note not found.", status_code=404)
        return APIResponse.success(data=GeneralNoteSerializer(note).data)

    def patch(self, request, pk):
        note = self._get_note_or_404(pk, request)
        if not note:
            return APIResponse.error(message="Note not found.", status_code=404)
        serializer = GeneralNoteSerializer(note, data=request.data, partial=True)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        serializer.save()
        return APIResponse.success(data=serializer.data, message="Note updated.")

    def delete(self, request, pk):
        note = self._get_note_or_404(pk, request)
        if not note:
            return APIResponse.error(message="Note not found.", status_code=404)
        note.delete()
        return APIResponse.success(message="Note deleted.")


class GeneralNotePinToggleView(APIView):
    """POST /notes/<pk>/pin/ – toggle the pinned state of a personal note."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            note = GeneralNote.objects.get(pk=pk, owner_central_id=_central_id(request))
        except GeneralNote.DoesNotExist:
            return APIResponse.error(message="Note not found.", status_code=404)

        note.is_pinned = not note.is_pinned
        note.save(update_fields=["is_pinned", "updated_at"])
        return APIResponse.success(
            data={"pinned": note.is_pinned},
            message="Pinned." if note.is_pinned else "Unpinned.",
        )


# ---------------------------------------------------------------------------
# Meetings
# ---------------------------------------------------------------------------


class MeetingListCreateView(APIView):
    """
    GET  /meetings/  – list meetings the authenticated user participates in.
    POST /meetings/  – create a new meeting.

    Query params (GET):
      search         – filter by title or location.
      participant_id – filter by a specific participant's central_id.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        cid = _central_id(request)

        meeting_ids = MeetingParticipant.objects.filter(central_id=cid).values_list(
            "meeting_id", flat=True
        )

        meetings = Meeting.objects.filter(id__in=meeting_ids).prefetch_related(
            "participants", "agenda_items"
        )

        search = request.query_params.get("search", "").strip()
        if search:
            meetings = meetings.filter(
                django_models.Q(title__icontains=search)
                | django_models.Q(location__icontains=search)
            )

        participant_filter = request.query_params.get("participant_id", "").strip()
        if participant_filter:
            meetings = meetings.filter(participants__central_id=participant_filter)

        meetings = list(meetings)

        context = _build_meeting_context(request, meetings)
        pinned_ids = context["pinned_meeting_ids"]

        # Pinned meetings first, then newest first
        meetings.sort(key=lambda m: (m.id not in pinned_ids, m.created_at.isoformat()))

        return APIResponse.success(
            data=MeetingListSerializer(meetings, many=True, context=context).data
        )

    def post(self, request):
        serializer = MeetingCreateSerializer(
            data=request.data,
            context={"central_id": _central_id(request), "request": request},
        )
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)

        meeting = serializer.save()
        logger.info(
            "Meeting created | central_id=%s meeting_id=%s",
            _central_id(request),
            meeting.pk,
        )

        # Reload with related data so the detail serializer is fully populated
        meeting = Meeting.objects.prefetch_related(
            "participants", "agenda_items", "notes"
        ).get(pk=meeting.pk)

        return APIResponse.success(
            data=MeetingDetailSerializer(
                meeting,
                context=_build_meeting_context(request, [meeting]),
            ).data,
            message="Meeting created.",
            status_code=201,
        )


class MeetingDetailView(APIView):
    """
    GET    /meetings/<pk>/  – full meeting detail (participants only).
    PATCH  /meetings/<pk>/  – update meeting (creator only).
    DELETE /meetings/<pk>/  – creator deletes; participant leaves.
    """

    permission_classes = [IsAuthenticated]

    def _get_as_participant(self, pk, request):
        try:
            meeting = Meeting.objects.prefetch_related(
                "participants", "agenda_items", "notes"
            ).get(pk=pk)
        except Meeting.DoesNotExist:
            return None, "not_found"

        if not meeting.participants.filter(central_id=_central_id(request)).exists():
            return None, "not_participant"

        return meeting, None

    def _get_as_creator(self, pk, request):
        try:
            return (
                Meeting.objects.get(pk=pk, creator_central_id=_central_id(request)),
                None,
            )
        except Meeting.DoesNotExist:
            return None, "not_found"

    def get(self, request, pk):
        meeting, err = self._get_as_participant(pk, request)
        if err == "not_found":
            return APIResponse.error(message="Meeting not found.", status_code=404)
        if err == "not_participant":
            return APIResponse.error(
                message="You are not a participant of this meeting.", status_code=403
            )
        return APIResponse.success(
            data=MeetingDetailSerializer(
                meeting,
                context=_build_meeting_context(request, [meeting]),
            ).data
        )

    def patch(self, request, pk):
        meeting, _ = self._get_as_creator(pk, request)
        if not meeting:
            return APIResponse.error(
                message="Meeting not found or you are not the creator.", status_code=404
            )

        serializer = MeetingUpdateSerializer(
            meeting,
            data=request.data,
            partial=True,
            context={"central_id": _central_id(request), "request": request},
        )
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)

        updated = serializer.save()
        updated = Meeting.objects.prefetch_related(
            "participants", "agenda_items", "notes"
        ).get(pk=updated.pk)

        return APIResponse.success(
            data=MeetingDetailSerializer(
                updated,
                context=_build_meeting_context(request, [updated]),
            ).data,
            message="Meeting updated.",
        )

    def delete(self, request, pk):
        cid = _central_id(request)

        # Creator deletes the whole meeting
        try:
            Meeting.objects.get(pk=pk, creator_central_id=cid).delete()
            return APIResponse.success(message="Meeting deleted.")
        except Meeting.DoesNotExist:
            pass

        # Non-creator leaves the meeting
        deleted, _ = MeetingParticipant.objects.filter(
            meeting_id=pk, central_id=cid
        ).delete()
        if deleted:
            return APIResponse.success(message="Removed from meeting.")

        return APIResponse.error(message="Meeting not found.", status_code=404)


class MeetingPinToggleView(APIView):
    """POST /meetings/<pk>/pin/ – toggle the pinned state of a meeting."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        cid = _central_id(request)
        if not MeetingParticipant.objects.filter(
            meeting_id=pk, central_id=cid
        ).exists():
            return APIResponse.error(message="Meeting not found.", status_code=404)

        pin, created = MeetingPin.objects.get_or_create(meeting_id=pk, central_id=cid)
        if not created:
            pin.delete()
            pinned = False
        else:
            pinned = True

        return APIResponse.success(
            data={"pinned": pinned},
            message="Pinned." if pinned else "Unpinned.",
        )


# ---------------------------------------------------------------------------
# Agenda Items
# ---------------------------------------------------------------------------


class AgendaItemCreateView(APIView):
    """POST /meetings/<pk>/agenda/ – add an agenda item (creator only)."""

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
        return APIResponse.success(
            data=AgendaItemSerializer(item).data,
            message="Agenda item added.",
            status_code=201,
        )


class AgendaItemDetailView(APIView):
    """
    PATCH  /meetings/<pk>/agenda/<item_id>/  – update an agenda item (creator only).
    DELETE /meetings/<pk>/agenda/<item_id>/  – delete an agenda item (creator only).
    """

    permission_classes = [IsAuthenticated]

    def _get_item_or_404(self, pk, item_id, request):
        try:
            return AgendaItem.objects.get(
                pk=item_id,
                meeting_id=pk,
                meeting__creator_central_id=_central_id(request),
            )
        except AgendaItem.DoesNotExist:
            return None

    def patch(self, request, pk, item_id):
        item = self._get_item_or_404(pk, item_id, request)
        if not item:
            return APIResponse.error(message="Agenda item not found.", status_code=404)
        serializer = AgendaItemUpdateSerializer(item, data=request.data, partial=True)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        serializer.save()
        return APIResponse.success(
            data=AgendaItemSerializer(item).data, message="Agenda item updated."
        )

    def delete(self, request, pk, item_id):
        item = self._get_item_or_404(pk, item_id, request)
        if not item:
            return APIResponse.error(message="Agenda item not found.", status_code=404)
        item.delete()
        return APIResponse.success(message="Agenda item deleted.")


# ---------------------------------------------------------------------------
# Meeting Notes
# ---------------------------------------------------------------------------


class MeetingNoteCreateView(APIView):
    """POST /meetings/<pk>/notes/ – add a note to a meeting (participants only)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        cid = _central_id(request)
        if not MeetingParticipant.objects.filter(
            meeting_id=pk, central_id=cid
        ).exists():
            return APIResponse.error(message="Meeting not found.", status_code=404)

        serializer = MeetingNoteSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)

        note = serializer.save(meeting_id=pk, created_by_central_id=cid)
        return APIResponse.success(
            data=MeetingNoteSerializer(note).data,
            message="Note added.",
            status_code=201,
        )


class MeetingNoteDetailView(APIView):
    """
    PATCH  /meetings/<pk>/notes/<note_id>/  – update own note.
    DELETE /meetings/<pk>/notes/<note_id>/  – delete own note.
    """

    permission_classes = [IsAuthenticated]

    def _get_note_or_404(self, note_id, request):
        try:
            return MeetingNote.objects.get(
                pk=note_id, created_by_central_id=_central_id(request)
            )
        except MeetingNote.DoesNotExist:
            return None

    def patch(self, request, pk, note_id):
        note = self._get_note_or_404(note_id, request)
        if not note:
            return APIResponse.error(message="Note not found.", status_code=404)
        serializer = MeetingNoteSerializer(note, data=request.data, partial=True)
        if not serializer.is_valid():
            return APIResponse.error(errors=serializer.errors)
        serializer.save()
        return APIResponse.success(
            data=MeetingNoteSerializer(note).data, message="Note updated."
        )

    def delete(self, request, pk, note_id):
        note = self._get_note_or_404(note_id, request)
        if not note:
            return APIResponse.error(message="Note not found.", status_code=404)
        note.delete()
        return APIResponse.success(message="Note deleted.")


class MeetingNotePinToggleView(APIView):
    """POST /meetings/<pk>/notes/<note_id>/pin/ – toggle pin on own note."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk, note_id):
        try:
            note = MeetingNote.objects.get(
                pk=note_id,
                meeting_id=pk,
                created_by_central_id=_central_id(request),
            )
        except MeetingNote.DoesNotExist:
            return APIResponse.error(message="Note not found.", status_code=404)

        note.is_pinned = not note.is_pinned
        note.save(update_fields=["is_pinned", "updated_at"])
        return APIResponse.success(
            data={"pinned": note.is_pinned},
            message="Pinned." if note.is_pinned else "Unpinned.",
        )


# ---------------------------------------------------------------------------
# Notes Tab (unified general + meeting notes)
# ---------------------------------------------------------------------------


class NotesTabView(APIView):
    """
    authenticated user, sorted pinned-first then oldest-first.

    Query params:
      search - filter by title / description for general notes, and by
               description / meeting title for meeting notes.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        cid = _central_id(request)
        search = request.query_params.get("search", "").strip()

        general_qs = GeneralNote.objects.filter(owner_central_id=cid)
        if search:
            general_qs = general_qs.filter(
                django_models.Q(title__icontains=search)
                | django_models.Q(description__icontains=search)
            )

        meeting_qs = MeetingNote.objects.filter(
            meeting__participants__central_id=cid
        ).select_related("meeting")
        if search:
            meeting_qs = meeting_qs.filter(
                django_models.Q(description__icontains=search)
                | django_models.Q(meeting__title__icontains=search)
            )

        unified = [
            {
                "id": n.id,
                "source": "general",
                "meeting_id": None,
                "meeting_title": None,
                "title": n.title,
                "description": n.description,
                "is_pinned": n.is_pinned,
                "created_at": n.created_at,
            }
            for n in general_qs
        ] + [
            {
                "id": n.id,
                "source": "meeting",
                "meeting_id": n.meeting.id,
                "meeting_title": n.meeting.title,
                "title": None,
                "description": n.description,
                "is_pinned": n.is_pinned,
                "created_at": n.created_at,
            }
            for n in meeting_qs
        ]

        unified.sort(key=lambda x: (not x["is_pinned"], x["created_at"]))
        return APIResponse.success(data=NotesTabSerializer(unified, many=True).data)
