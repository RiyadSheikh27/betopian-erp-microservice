from rest_framework import serializers

from .models import Meeting, MeetingParticipant, AgendaItem, MeetingNote, GeneralNote


# ---------------------------------------------------------------------------
# General Notes
# ---------------------------------------------------------------------------


class GeneralNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneralNote
        fields = ("id", "title", "description", "is_pinned", "created_at", "updated_at")
        read_only_fields = ("id", "is_pinned", "created_at", "updated_at")


# ---------------------------------------------------------------------------
# Agenda Items
# ---------------------------------------------------------------------------


class AgendaItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgendaItem
        fields = ("id", "title", "is_done", "created_at")
        read_only_fields = ("id", "created_at")


class AgendaItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgendaItem
        fields = ("title",)


class AgendaItemUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgendaItem
        fields = ("title", "is_done")


# ---------------------------------------------------------------------------
# Meeting Notes
# ---------------------------------------------------------------------------


class MeetingNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingNote
        fields = ("id", "description", "created_by_central_id", "is_pinned", "created_at")
        read_only_fields = ("id", "created_by_central_id", "is_pinned", "created_at")


# ---------------------------------------------------------------------------
# Participants (read-only, used inside meeting serializers)
# ---------------------------------------------------------------------------


class ParticipantSerializer(serializers.Serializer):
    """
    Read-only representation of a meeting participant.

    Profile data is merged from two sources (priority order):
      1. Live profile fetched from the central employee-directory API
         (passed via serializer context as ``participant_profiles``).
      2. Cached fields stored on the ``MeetingParticipant`` row itself.

    This means the list will always show *something* even when the central
    API is unavailable, and will automatically pick up live data when it is.
    """

    central_id = serializers.IntegerField()
    employee_id = serializers.CharField()
    name = serializers.CharField()
    designation = serializers.CharField()
    avatar_url = serializers.CharField()
    is_creator = serializers.BooleanField()


# ---------------------------------------------------------------------------
# Meetings – list
# ---------------------------------------------------------------------------


class MeetingListSerializer(serializers.ModelSerializer):
    """
    Compact meeting representation used in list endpoints.

    Context expected from the view:
      - ``participant_profiles``: dict[str(meeting_id), dict[central_id, profile]]
      - ``pinned_meeting_ids``:   set[UUID]
    """

    participants = serializers.SerializerMethodField()
    total_people = serializers.SerializerMethodField()
    agenda_done = serializers.SerializerMethodField()
    agenda_total = serializers.SerializerMethodField()
    agenda_completion_percent = serializers.SerializerMethodField()
    is_pinned = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = (
            "id",
            "creator_central_id",
            "title",
            "scheduled_at",
            "location",
            "participants",
            "total_people",
            "agenda_done",
            "agenda_total",
            "agenda_completion_percent",
            "is_pinned",
            "created_at",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _live_profile(self, meeting_id, central_id):
        """Return the live profile dict for one participant, or {}."""
        all_profiles = self.context.get("participant_profiles", {})
        return all_profiles.get(str(meeting_id), {}).get(central_id) or {}

    # ------------------------------------------------------------------
    # Field methods
    # ------------------------------------------------------------------

    def get_participants(self, obj):
        creator_id = obj.creator_central_id
        result = []

        for participant in obj.participants.all():
            profile = self._live_profile(obj.id, participant.central_id)

            name = (
                profile.get("name")
                or participant.username
                or f"User {participant.central_id}"
            )
            if participant.central_id == creator_id:
                name = f"{name} (Meeting Creator)"

            result.append(
                {
                    "central_id": participant.central_id,
                    "employee_id": profile.get("employee_code") or participant.employee_id or "",
                    "name": name,
                    "designation": (
                        profile.get("job_title")
                        or profile.get("department")
                        or participant.designation
                        or ""
                    ),
                    "avatar_url": profile.get("avatar_url") or participant.avatar_url or "",
                    "is_creator": participant.central_id == creator_id,
                }
            )

        # Creator always first
        result.sort(key=lambda x: not x["is_creator"])
        return result

    def get_total_people(self, obj):
        return obj.participants.count()

    def get_agenda_done(self, obj):
        return obj.agenda_items.filter(is_done=True).count()

    def get_agenda_total(self, obj):
        return obj.agenda_items.count()

    def get_agenda_completion_percent(self, obj):
        total = obj.agenda_items.count()
        if not total:
            return 0
        done = obj.agenda_items.filter(is_done=True).count()
        return round((done / total) * 100)

    def get_is_pinned(self, obj):
        return obj.id in self.context.get("pinned_meeting_ids", set())


# ---------------------------------------------------------------------------
# Meetings – detail
# ---------------------------------------------------------------------------


class MeetingDetailSerializer(MeetingListSerializer):
    """
    Full meeting representation including agenda items, notes, and a
    cross-meeting agenda summary for the requesting user.
    """

    agenda_items = AgendaItemSerializer(many=True, read_only=True)
    notes = MeetingNoteSerializer(many=True, read_only=True)
    all_meetings_agenda = serializers.SerializerMethodField()

    class Meta(MeetingListSerializer.Meta):
        fields = MeetingListSerializer.Meta.fields + (
            "agenda_items",
            "notes",
            "all_meetings_agenda",
            "updated_at",
        )

    def get_all_meetings_agenda(self, obj):
        """Aggregate agenda stats across every meeting the current user belongs to."""
        request = self.context.get("request")
        central_id = getattr(request.user, "central_id", None) if request else None
        if not central_id:
            return None

        meeting_ids = MeetingParticipant.objects.filter(
            central_id=central_id
        ).values_list("meeting_id", flat=True)

        total = AgendaItem.objects.filter(meeting_id__in=meeting_ids).count()
        done = AgendaItem.objects.filter(
            meeting_id__in=meeting_ids, is_done=True
        ).count()
        pct = round((done / total) * 100) if total else 0

        return {
            "done": done,
            "total": total,
            "completion_percent": pct,
            "label": f"{done}/{total} · {pct}%",
        }


# ---------------------------------------------------------------------------
# Meetings – write
# ---------------------------------------------------------------------------


class MeetingWriteSerializer(serializers.ModelSerializer):
    """
    Shared base for create / update.  Subclasses implement ``save`` logic.

    ``participants`` accepts a list of **central_id** integers.  The creator
    is always added automatically; duplicates in the payload are ignored.
    """

    participants = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        help_text="List of central_id integers. Creator is always included.",
    )

    class Meta:
        model = Meeting
        fields = ("title", "scheduled_at", "location", "participants")


class MeetingCreateSerializer(MeetingWriteSerializer):
    def create(self, validated_data):
        from apps.authentication.backends import fetch_central_profiles_bulk

        participant_ids = set(validated_data.pop("participants", [])) | {
            self.context["central_id"]
        }
        creator_id = self.context["central_id"]
        token, session_id = self._credentials()

        meeting = Meeting.objects.create(
            creator_central_id=creator_id, **validated_data
        )

        profiles = fetch_central_profiles_bulk(list(participant_ids), token, session_id)
        MeetingParticipant.objects.bulk_create(
            self._build_participant(meeting, cid, profiles.get(cid), creator_id)
            for cid in participant_ids
        )
        return meeting

    def _credentials(self):
        request = self.context.get("request")
        token = getattr(request.user, "central_access_token", "") if request else ""
        session_id = request.COOKIES.get("session_id", "") if request else ""
        return token, session_id

    @staticmethod
    def _build_participant(meeting, central_id, profile, creator_id):
        from apps.mom.views import _profile_to_participant_fields

        fields = _profile_to_participant_fields(profile) if profile else {}
        return MeetingParticipant(
            meeting=meeting,
            central_id=central_id,
            is_creator=(central_id == creator_id),
            **fields,
        )


class MeetingUpdateSerializer(MeetingWriteSerializer):
    participants = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
    )

    def update(self, instance, validated_data):
        from apps.authentication.backends import fetch_central_profiles_bulk
        from apps.mom.views import _profile_to_participant_fields

        participant_ids = validated_data.pop("participants", None)
        creator_id = self.context["central_id"]

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if participant_ids is not None:
            participant_ids = set(participant_ids) | {creator_id}
            token, session_id = self._credentials()

            # Remove anyone no longer in the list
            instance.participants.exclude(central_id__in=participant_ids).delete()

            existing_ids = set(
                instance.participants.values_list("central_id", flat=True)
            )
            new_ids = participant_ids - existing_ids

            if new_ids:
                profiles = fetch_central_profiles_bulk(list(new_ids), token, session_id)
                MeetingParticipant.objects.bulk_create(
                    MeetingParticipant(
                        meeting=instance,
                        central_id=cid,
                        is_creator=(cid == creator_id),
                        **(_profile_to_participant_fields(profiles.get(cid)) if profiles.get(cid) else {}),
                    )
                    for cid in new_ids
                )

        return instance

    def _credentials(self):
        request = self.context.get("request")
        token = getattr(request.user, "central_access_token", "") if request else ""
        session_id = request.COOKIES.get("session_id", "") if request else ""
        return token, session_id


# ---------------------------------------------------------------------------
# Notes Tab (unified view)
# ---------------------------------------------------------------------------


class NotesTabSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    source = serializers.CharField()
    meeting_id = serializers.UUIDField(allow_null=True)
    meeting_title = serializers.CharField(allow_null=True)
    title = serializers.CharField(allow_null=True)
    description = serializers.CharField()
    is_pinned = serializers.BooleanField()
    created_at = serializers.DateTimeField()