from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Conversation,
    ConversationParticipant,
    Message,
    MessageMedia,
    MessageReaction,
    MessageStatus,
)

class ConversationParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)
    show_change_link = True


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    show_change_link = True

    readonly_fields = (
        "sender",
        "type",
        "body",
        "is_edited",
        "is_deleted",
        "created_at",
    )

    fields = (
        "sender",
        "type",
        "body",
        "is_edited",
        "is_deleted",
        "created_at",
    )


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "type",
        "community",
        "participant_count",
        "message_count",
        "last_activity",
    )

    list_filter = ("type",)
    search_fields = ("community__name",)

    autocomplete_fields = (
        "community",
        "last_message",
    )

    readonly_fields = (
        "participant_summary",
        "message_summary",
        "media_summary",
        "reaction_summary",
        "status_summary",
        "created_at",
        "updated_at",
        "last_activity",
    )

    inlines = (
        ConversationParticipantInline,
        MessageInline,
    )

    fieldsets = (
        (
            "Conversation",
            {
                "fields": (
                    "type",
                    "community",
                    "last_message",
                    "last_activity",
                )
            },
        ),
        ("Participants", {"fields": ("participant_summary",)}),
        ("Messages", {"fields": ("message_summary",)}),
        ("Media", {"fields": ("media_summary",)}),
        ("Reactions", {"fields": ("reaction_summary",)}),
        ("Statuses", {"fields": ("status_summary",)}),
        (
            "Audit",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="Participants")
    def participant_count(self, obj):
        return obj.participants.count()

    @admin.display(description="Messages")
    def message_count(self, obj):
        return obj.messages.count()

    @admin.display(description="Participants")
    def participant_summary(self, obj):
        participants = obj.participants.select_related("user")

        rows = [f"• {p.user}" for p in participants]

        return format_html("<br>".join(rows) if rows else "No participants")

    @admin.display(description="Recent Messages")
    def message_summary(self, obj):
        messages = obj.messages.select_related("sender").order_by("-created_at")[:20]

        rows = [
            f"• [{m.sender}] {m.body[:80] if m.body else '(empty)'}" for m in messages
        ]

        return format_html("<br>".join(rows) if rows else "No messages")

    @admin.display(description="Media")
    def media_summary(self, obj):
        media = MessageMedia.objects.filter(message__conversation=obj).select_related(
            "message"
        )[:50]

        rows = [f"• {m.media_type} | {m.file_name or m.file.name}" for m in media]

        return format_html("<br>".join(rows) if rows else "No media")

    @admin.display(description="Reactions")
    def reaction_summary(self, obj):
        reactions = MessageReaction.objects.filter(
            message__conversation=obj
        ).select_related("user")[:50]

        rows = [f"• {r.user} - {r.reaction}" for r in reactions]

        return format_html("<br>".join(rows) if rows else "No reactions")

    @admin.display(description="Statuses")
    def status_summary(self, obj):
        statuses = MessageStatus.objects.filter(
            message__conversation=obj
        ).select_related("recipient")[:50]

        rows = [
            f"• {s.recipient} | Delivered={s.is_delivered} | Read={s.is_read}"
            for s in statuses
        ]

        return format_html("<br>".join(rows) if rows else "No statuses")



class MessageMediaInline(admin.TabularInline):
    model = MessageMedia
    extra = 0


class MessageReactionInline(admin.TabularInline):
    model = MessageReaction
    extra = 0
    autocomplete_fields = ("user",)


class MessageStatusInline(admin.TabularInline):
    model = MessageStatus
    extra = 0
    autocomplete_fields = ("recipient",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "sender",
        "type",
        "is_deleted",
        "is_edited",
        "created_at",
    )

    list_filter = (
        "type",
        "is_deleted",
        "is_edited",
    )

    search_fields = (
        "body",
        "sender__username",
        "sender__email",
    )

    autocomplete_fields = (
        "conversation",
        "sender",
        "reply_to",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    inlines = (
        MessageMediaInline,
        MessageReactionInline,
        MessageStatusInline,
    )



@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "user", "created_at")
    autocomplete_fields = ("conversation", "user")


@admin.register(MessageMedia)
class MessageMediaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "message",
        "media_type",
        "file_name",
        "file_size",
        "order",
    )


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "user", "reaction")
    autocomplete_fields = ("message", "user")


@admin.register(MessageStatus)
class MessageStatusAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "message",
        "recipient",
        "is_delivered",
        "is_read",
    )

    autocomplete_fields = (
        "message",
        "recipient",
    )
