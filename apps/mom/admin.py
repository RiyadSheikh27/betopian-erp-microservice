# from django.contrib import admin
# from .models import GeneralNote, Meeting, AgendaItem, MeetingNote


# @admin.register(GeneralNote)
# class GeneralNoteAdmin(admin.ModelAdmin):
#     list_display = ["id", "title", "user", "created_at"]
#     search_fields = ["title", "user__username"]


# class AgendaItemInline(admin.TabularInline):
#     model = AgendaItem
#     extra = 0


# class MeetingNoteInline(admin.TabularInline):
#     model = MeetingNote
#     extra = 0
#     readonly_fields = ["created_at"]


# @admin.register(Meeting)
# class MeetingAdmin(admin.ModelAdmin):
#     list_display = ["id", "title", "user", "scheduled_at", "location"]
#     search_fields = ["title", "user__username"]
#     inlines = [AgendaItemInline, MeetingNoteInline]


# @admin.register(AgendaItem)
# class AgendaItemAdmin(admin.ModelAdmin):
#     list_display = ["id", "title", "meeting", "is_done"]
#     list_filter = ["is_done"]


# @admin.register(MeetingNote)
# class MeetingNoteAdmin(admin.ModelAdmin):
#     list_display = ["id", "meeting", "created_at"]
#     readonly_fields = ["created_at"]
