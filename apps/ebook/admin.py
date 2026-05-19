from django.contrib import admin
from .models import EbookTitle, Ebook


@admin.register(EbookTitle)
class EbookTitleAdmin(admin.ModelAdmin):
    list_display = ("id", "ebook_title", "created_at")
    search_fields = ("ebook_title",)
    ordering = ("ebook_title",)


class EbookInline(admin.TabularInline):
    """Show ebooks inline when editing a title."""
    model = Ebook
    extra = 1
    fields = ("file", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Ebook)
class EbookAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "file", "created_at")
    list_filter = ("title",)
    search_fields = ("title__ebook_title",)
    autocomplete_fields = ("title",)
    ordering = ("-created_at",)


# Also show ebooks inline on the title page
EbookTitleAdmin.inlines = [EbookInline]