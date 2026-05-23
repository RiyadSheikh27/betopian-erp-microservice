from django.contrib import admin
from .models import EbookTitle, Ebook


@admin.register(EbookTitle)
class EbookTitleAdmin(admin.ModelAdmin):
    list_display = ("id", "category_title", "category_image", "created_at")
    search_fields = ("category_title",)
    ordering = ("category_title",)


class EbookInline(admin.TabularInline):
    """Show ebooks inline when editing a title."""

    model = Ebook
    extra = 1
    fields = ("file", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Ebook)
class EbookAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "file_name", "created_at")
    list_filter = ("category",)
    search_fields = ("category__category_title",)
    autocomplete_fields = ("category",)
    ordering = ("-created_at",)


# Also show ebooks inline on the title page
EbookTitleAdmin.inlines = [EbookInline]
