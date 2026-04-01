from django.contrib import admin

from .models import Chapter, Discipline


@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "github_repo", "published", "order"]
    list_editable = ["published", "order"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ["title", "discipline", "chapter_type", "published", "cached_at"]
    list_filter = ["discipline", "chapter_type", "published"]
    search_fields = ["title", "github_repo", "description"]
    readonly_fields = ["cached_at"]
    list_per_page = 50
