from rest_framework import serializers
from .models import Meeting, MeetingParticipant, AgendaItem, MeetingNote, GeneralNote


class GeneralNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneralNote
        fields = ("id", "title", "description", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


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

class MeetingNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MeetingNote
        fields = ("id", "description", "created_by_central_id", "created_at")
        read_only_fields = ("id", "created_by_central_id", "created_at")


class MeetingListSerializer(serializers.ModelSerializer):
    """Compact meeting list — summary counts only, no nested items."""

    participants = serializers.SerializerMethodField()
    total_people = serializers.SerializerMethodField()
    agenda_done = serializers.SerializerMethodField()
    agenda_total = serializers.SerializerMethodField()
    agenda_completion_percent = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = (
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
        )

    def get_participants(self, obj):
        return list(obj.participants.values_list("central_id", flat=True))

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
        return round((obj.agenda_items.filter(is_done=True).count() / total) * 100)


class MeetingDetailSerializer(MeetingListSerializer):
    """Full meeting detail — includes agenda items, notes and all-meetings stats."""

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
        """
        Aggregated agenda stats across ALL meetings the requesting user is part of.
        Used for the summary bar in the UI.
        """
        request = self.context.get("request")
        central_id = getattr(request.user, "central_id", None)
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


class MeetingCreateSerializer(serializers.ModelSerializer):
    participants = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )

    class Meta:
        model = Meeting
        fields = ("title", "scheduled_at", "location", "participants")

    def create(self, validated_data):
        participants = validated_data.pop("participants", [])
        creator_id = self.context["central_id"]
        meeting = Meeting.objects.create(
            creator_central_id=creator_id, **validated_data
        )

        # Add creator + all participants — deduplicate in case creator added themselves
        participant_ids = set(participants) | {creator_id}
        MeetingParticipant.objects.bulk_create(
            [
                MeetingParticipant(
                    meeting=meeting,
                    central_id=cid,
                    is_creator=(cid == creator_id),
                )
                for cid in participant_ids
            ]
        )
        return meeting


class MeetingUpdateSerializer(serializers.ModelSerializer):
    """
    Creator only. participants replaces the full list when provided.
    Creator is always kept — cannot remove themselves via this endpoint.
    """

    participants = serializers.ListField(
        child=serializers.IntegerField(), required=False
    )

    class Meta:
        model = Meeting
        fields = ("title", "scheduled_at", "location", "participants")

    def update(self, instance, validated_data):
        participants = validated_data.pop("participants", None)
        creator_id = self.context["central_id"]

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if participants is not None:
            # Replace participant list — always keep creator
            participant_ids = set(participants) | {creator_id}
            instance.participants.exclude(central_id__in=participant_ids).delete()
            existing = set(instance.participants.values_list("central_id", flat=True))
            new_ids = participant_ids - existing
            MeetingParticipant.objects.bulk_create(
                [
                    MeetingParticipant(
                        meeting=instance,
                        central_id=cid,
                        is_creator=(cid == creator_id),
                    )
                    for cid in new_ids
                ]
            )
        return instance


class NotesTabSerializer(serializers.Serializer):
    """Unified shape for general notes and meeting notes combined."""

    id = serializers.UUIDField()
    source = serializers.CharField()  # "general" | "meeting"
    meeting_id = serializers.UUIDField(allow_null=True)
    meeting_title = serializers.CharField(allow_null=True)
    title = serializers.CharField(allow_null=True)
    description = serializers.CharField()
    created_at = serializers.DateTimeField()
