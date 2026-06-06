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

# INLINES

class ConversationParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0
    autocomplete_fields = ("user",)
    readonly_fields = (
        "user",
        "is_online",
        "last_seen",
        "last_read_message",
        "created_at",
    )
    can_delete = False


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    show_change_link = True
    autocomplete_fields = ("sender", "reply_to")
    readonly_fields = (
        "sender",
        "type",
        "body",
        "is_edited",
        "is_deleted",
        "created_at",
    )


# CONVERSATION


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

    inlines = [
        ConversationParticipantInline,
        MessageInline,
    ]

    fieldsets = (
        (
            "Conversation Info",
            {
                "fields": (
                    "type",
                    "community",
                    "last_message",
                    "last_activity",
                )
            },
        ),
        (
            "Participants",
            {"fields": ("participant_summary",)},
        ),
        (
            "Messages",
            {"fields": ("message_summary",)},
        ),
        (
            "Media",
            {"fields": ("media_summary",)},
        ),
        (
            "Reactions",
            {"fields": ("reaction_summary",)},
        ),
        (
            "Statuses",
            {"fields": ("status_summary",)},
        ),
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

    # List display helpers

    @admin.display(description="Participants")
    def participant_count(self, obj):
        return obj.participants.count()

    @admin.display(description="Messages")
    def message_count(self, obj):
        return obj.messages.count()

    # Detail page sections

    @admin.display(description="Participants")
    def participant_summary(self, obj):
        participants = obj.participants.select_related("user")

        rows = [
            f"• {p.user} | Online: {'Yes' if p.is_online else 'No'}"
            for p in participants
        ]

        return format_html("<br>".join(rows) if rows else "No participants")

    @admin.display(description="Messages")
    def message_summary(self, obj):
        messages = obj.messages.select_related("sender").order_by("-created_at")[:20]

        rows = [f"• [{m.sender}] {m.body[:80] or '(empty)'}" for m in messages]

        return format_html("<br>".join(rows) if rows else "No messages")

    @admin.display(description="Media")
    def media_summary(self, obj):
        media = MessageMedia.objects.filter(message__conversation=obj).select_related(
            "message"
        )[:50]

        rows = [f"• {m.media_type} | {m.file_name}" for m in media]

        return format_html("<br>".join(rows) if rows else "No media")

    @admin.display(description="Reactions")
    def reaction_summary(self, obj):
        reactions = MessageReaction.objects.filter(
            message__conversation=obj
        ).select_related("user")[:50]

        rows = [f"• {r.user} → {r.reaction}" for r in reactions]

        return format_html("<br>".join(rows) if rows else "No reactions")

    @admin.display(description="Statuses")
    def status_summary(self, obj):
        statuses = MessageStatus.objects.filter(
            message__conversation=obj
        ).select_related("recipient")[:50]

        rows = [
            f"• {s.recipient} | Read={s.is_read} | Delivered={s.is_delivered}"
            for s in statuses
        ]

        return format_html("<br>".join(rows) if rows else "No statuses")


# MESSAGE


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "sender",
        "type",
        "is_deleted",
        "created_at",
    )

    list_filter = (
        "type",
        "is_deleted",
        "is_edited",
    )

    search_fields = (
        "body",
        "sender__email",
        "sender__username",
    )

    autocomplete_fields = (
        "conversation",
        "sender",
        "reply_to",
    )
