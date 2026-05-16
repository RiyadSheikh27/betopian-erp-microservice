from rest_framework import serializers
from .models import GeneralNote, Meeting, AgendaItem, MeetingNote

# ---------------------------------------------------------------------------
# General Note
# ---------------------------------------------------------------------------


class GeneralNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneralNote
        fields = ["id", "title", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# Agenda Item
# ---------------------------------------------------------------------------


class AgendaItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgendaItem
        fields = ["id", "title", "is_done", "created_at"]
        read_only_fields = ["id", "created_at"]


# ---------------------------------------------------------------------------
# Meeting Note
# ---------------------------------------------------------------------------


class MeetingNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingNote
        fields = ["id", "description", "created_at"]
        read_only_fields = ["id", "created_at"]


# ---------------------------------------------------------------------------
# Meeting — Create
# ---------------------------------------------------------------------------


class MeetingCreateSerializer(serializers.ModelSerializer):
    """
    Used when creating a meeting.
    Participants are accepted as a plain list of name strings.
    Agenda starts empty — items are added separately after creation.
    """

    participants = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False,
        default=list,
    )

    class Meta:
        model = Meeting
        fields = ["id", "title", "scheduled_at", "location", "participants"]
        read_only_fields = ["id"]


# ---------------------------------------------------------------------------
# Meeting — Update
# ---------------------------------------------------------------------------


class MeetingUpdateSerializer(serializers.ModelSerializer):
    """
    Allows editing title, schedule, location, and the participants list.
    Send the full updated participants list to replace the existing one.
    """

    participants = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False,
    )

    class Meta:
        model = Meeting
        fields = ["title", "scheduled_at", "location", "participants"]


# ---------------------------------------------------------------------------
# Meeting — List (lightweight)
# ---------------------------------------------------------------------------


class MeetingListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the meetings list screen."""

    total_people = serializers.SerializerMethodField()
    agenda_done = serializers.SerializerMethodField()
    agenda_total = serializers.SerializerMethodField()
    agenda_completion_percent = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "scheduled_at",
            "location",
            "participants",
            "total_people",
            "agenda_done",
            "agenda_total",
            "agenda_completion_percent",
            "created_at",
        ]

    def get_total_people(self, obj):
        return len(obj.participants)

    def get_agenda_done(self, obj):
        return obj.agenda_items.filter(is_done=True).count()

    def get_agenda_total(self, obj):
        return obj.agenda_items.count()

    def get_agenda_completion_percent(self, obj):
        total = obj.agenda_items.count()
        if total == 0:
            return 0
        done = obj.agenda_items.filter(is_done=True).count()
        return round((done / total) * 100)


# ---------------------------------------------------------------------------
# Meeting — Detail (full)
# ---------------------------------------------------------------------------


class MeetingDetailSerializer(serializers.ModelSerializer):
    agenda_items = AgendaItemSerializer(many=True, read_only=True)
    notes = MeetingNoteSerializer(many=True, read_only=True)

    total_people = serializers.SerializerMethodField()
    agenda_done = serializers.SerializerMethodField()
    agenda_total = serializers.SerializerMethodField()
    agenda_completion_percent = serializers.SerializerMethodField()
    all_meetings_agenda = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "scheduled_at",
            "location",
            "participants",
            "total_people",
            "agenda_done",
            "agenda_total",
            "agenda_completion_percent",
            "all_meetings_agenda",
            "agenda_items",
            "notes",
            "created_at",
            "updated_at",
        ]

    def get_total_people(self, obj):
        return len(obj.participants)

    def get_agenda_done(self, obj):
        return obj.agenda_items.filter(is_done=True).count()

    def get_agenda_total(self, obj):
        return obj.agenda_items.count()

    def get_agenda_completion_percent(self, obj):
        total = obj.agenda_items.count()
        if total == 0:
            return 0
        done = obj.agenda_items.filter(is_done=True).count()
        return round((done / total) * 100)

    def get_all_meetings_agenda(self, obj):
        user_meetings = Meeting.objects.filter(user=obj.user)
        total = AgendaItem.objects.filter(meeting__in=user_meetings).count()
        done = AgendaItem.objects.filter(
            meeting__in=user_meetings, is_done=True
        ).count()
        percent = round((done / total) * 100) if total > 0 else 0
        return {
            "done": done,
            "total": total,
            "completion_percent": percent,
            "label": f"{done}/{total} · {percent}%",
        }
