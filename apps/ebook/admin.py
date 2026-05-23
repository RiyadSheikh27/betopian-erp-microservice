from django.contrib import admin
from .models import EbookTitle, Ebook


class EbookInline(admin.TabularInline):
    model = Ebook
    extra = 1
    fields = ("file_name", "file")
    readonly_fields = ("created_at",)


@admin.register(EbookTitle)
class EbookTitleAdmin(admin.ModelAdmin):
    list_display = ("id", "category_title", "category_image", "created_at")
    search_fields = ("category_title",)
    ordering = ("category_title",)
    inlines = [EbookInline]


@admin.register(Ebook)
class EbookAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "file_name", "created_at")
    list_filter = ("category",)
    search_fields = ("category__category_title",)
    autocomplete_fields = ("category",)
    ordering = ("-created_at",)
