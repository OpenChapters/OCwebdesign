from django.contrib import admin

from .models import Chapter, Discipline, Example, ExampleFigure


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


class ExampleFigureInline(admin.TabularInline):
    model = ExampleFigure
    extra = 0
    fields = ["original_filename", "caption", "order", "file"]
    readonly_fields = ["created_at"]


@admin.register(Example)
class ExampleAdmin(admin.ModelAdmin):
    list_display = ["id", "primary_chapter", "author", "difficulty", "status", "created_at"]
    list_filter = ["status", "difficulty", "primary_chapter"]
    search_fields = ["statement_tex", "solution_tex"]
    autocomplete_fields = ["primary_chapter", "chapters", "author"]
    readonly_fields = ["created_at", "updated_at", "preview_built_at"]
    inlines = [ExampleFigureInline]
    list_per_page = 50
