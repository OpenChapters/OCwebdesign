from django.contrib import admin

from .models import Chapter


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ["title", "github_repo", "cached_at"]
    search_fields = ["title", "github_repo", "description"]
    readonly_fields = ["cached_at"]
    list_per_page = 50
