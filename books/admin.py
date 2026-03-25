from django.contrib import admin

from .models import Book, BookChapter, BookPart, BuildJob


class BookPartInline(admin.TabularInline):
    model = BookPart
    extra = 0
    fields = ["title", "order"]


class BookChapterInline(admin.TabularInline):
    model = BookChapter
    extra = 0
    fields = ["chapter", "order"]
    autocomplete_fields = ["chapter"]


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "status", "created_at", "updated_at"]
    list_filter = ["status"]
    search_fields = ["title", "user__email"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [BookPartInline]


@admin.register(BookPart)
class BookPartAdmin(admin.ModelAdmin):
    list_display = ["title", "book", "order"]
    search_fields = ["title", "book__title"]
    inlines = [BookChapterInline]


@admin.register(BuildJob)
class BuildJobAdmin(admin.ModelAdmin):
    list_display = ["book", "celery_task_id", "started_at", "finished_at"]
    readonly_fields = ["started_at", "finished_at", "celery_task_id", "pdf_path", "log_output", "error_message"]
    search_fields = ["book__title"]
