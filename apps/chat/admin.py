from django.contrib import admin

from .models import (
    Conversation,
    ConversationParticipant,
    Message,
    MessageMedia,
    MessageReaction,
    MessageStatus,
    CallLog,
)

@admin.register(
    Conversation,
    ConversationParticipant,
    Message,
    MessageMedia,
    MessageReaction,
    MessageStatus,
    CallLog,
)
class ChatAdmin(admin.ModelAdmin):
    list_per_page = 50
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")

    def get_list_display(self, request):
        model = self.model

        if model == Conversation:
            return (
                "id",
                "type",
                "community",
                "last_message",
                "last_activity",
                "created_at",
            )

        if model == ConversationParticipant:
            return (
                "id",
                "conversation",
                "user",
                "created_at",
            )

        if model == Message:
            return (
                "id",
                "conversation",
                "sender",
                "type",
                "is_edited",
                "is_deleted",
                "created_at",
            )

        if model == MessageMedia:
            return (
                "id",
                "message",
                "media_type",
                "file_name",
                "file_size",
                "order",
                "created_at",
            )

        if model == MessageReaction:
            return (
                "id",
                "message",
                "user",
                "reaction",
                "created_at",
            )

        if model == MessageStatus:
            return (
                "id",
                "message",
                "recipient",
                "is_delivered",
                "is_read",
                "read_at",
                "created_at",
            )

        if model == CallLog:
            return (
                "id",
                "conversation",
                "caller",
                "receiver",
                "call_type",
                "status",
                "duration",
                "created_at",
            )

        return ("id",)

    def get_list_filter(self, request):
        model = self.model

        if model == Conversation:
            return ("type", "created_at")

        if model == Message:
            return ("type", "is_edited", "is_deleted", "created_at")

        if model == MessageMedia:
            return ("media_type", "created_at")

        if model == MessageReaction:
            return ("reaction", "created_at")

        if model == MessageStatus:
            return ("is_delivered", "is_read", "created_at")

        if model == CallLog:
            return ("call_type", "status", "created_at")

        return ("created_at",)

    def get_search_fields(self, request):
        model = self.model

        if model == Conversation:
            return ("id",)

        if model == ConversationParticipant:
            return (
                "user__email",
                "user__username",
            )

        if model == Message:
            return (
                "body",
                "sender__email",
                "sender__username",
            )

        if model == MessageMedia:
            return ("file_name",)

        if model == MessageReaction:
            return (
                "user__email",
                "user__username",
            )

        if model == MessageStatus:
            return (
                "recipient__email",
                "recipient__username",
            )

        if model == CallLog:
            return (
                "caller__email",
                "receiver__email",
            )

        return ()
