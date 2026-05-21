from django.contrib import admin
from .models import Meeting, MeetingParticipant, AgendaItem, MeetingNote, GeneralNote

""" Admin configuration for Meeting and Notes (MoM) microservice. """


class MeetingParticipantInline(admin.TabularInline):
    model = MeetingParticipant
    extra = 0
    readonly_fields = ("central_id", "is_creator", "created_at")


class AgendaItemInline(admin.TabularInline):
    model = AgendaItem
    extra = 0
    readonly_fields = ("created_at",)


class MeetingNoteInline(admin.TabularInline):
    model = MeetingNote
    extra = 0
    readonly_fields = ("description", "created_by_central_id", "created_at")


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ("title", "creator_central_id", "scheduled_at", "created_at")
    search_fields = ("title", "creator_central_id")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [MeetingParticipantInline, AgendaItemInline, MeetingNoteInline]


@admin.register(GeneralNote)
class GeneralNoteAdmin(admin.ModelAdmin):
    list_display = ("title", "owner_central_id", "created_at")
    search_fields = ("title", "owner_central_id")
    readonly_fields = ("id", "created_at", "updated_at")
