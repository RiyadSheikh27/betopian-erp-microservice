from django.contrib import admin
from .models import (
    Meeting,
    MeetingPin,
    MeetingParticipant,
    AgendaItem,
    MeetingNote,
    GeneralNote,
)

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


@admin.register(MeetingPin)
class MeetingPinAdmin(admin.ModelAdmin):
    list_display = ("meeting", "central_id", "created_at")
    search_fields = ("meeting__title", "central_id")
    autocomplete_fields = ("meeting",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(MeetingParticipant)
class MeetingParticipantAdmin(admin.ModelAdmin):
    list_display = (
        "meeting",
        "central_id",
        "username",
        "employee_code",
        "is_creator",
        "created_at",
    )
    list_filter = ("is_creator", "created_at")
    search_fields = ("username", "employee_code", "central_id", "meeting__title")
    autocomplete_fields = ("meeting",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(AgendaItem)
class AgendaItemAdmin(admin.ModelAdmin):
    list_display = ("meeting", "title", "is_done", "created_at")
    list_filter = ("is_done", "created_at")
    search_fields = ("title", "meeting__title")
    autocomplete_fields = ("meeting",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(MeetingNote)
class MeetingNoteAdmin(admin.ModelAdmin):
    list_display = (
        "meeting",
        "created_by_central_id",
        "is_pinned",
        "created_at",
    )
    list_filter = ("is_pinned", "created_at")
    search_fields = ("description", "meeting__title", "created_by_central_id")
    autocomplete_fields = ("meeting",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(GeneralNote)
class GeneralNoteAdmin(admin.ModelAdmin):
    list_display = ("title", "owner_central_id", "created_at")
    search_fields = ("title", "owner_central_id")
    readonly_fields = ("id", "created_at", "updated_at")
