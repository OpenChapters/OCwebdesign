from catalog.models import Chapter
from catalog.serializers import ChapterSerializer
from rest_framework import serializers

from .models import Book, BookChapter, BookPart, BuildJob


class BookChapterSerializer(serializers.ModelSerializer):
    chapter_detail = ChapterSerializer(source="chapter", read_only=True)
    chapter_id = serializers.PrimaryKeyRelatedField(
        source="chapter",
        queryset=Chapter.objects.all(),
        write_only=True,
    )

    class Meta:
        model = BookChapter
        fields = ["id", "order", "chapter_id", "chapter_detail"]


class BookPartSerializer(serializers.ModelSerializer):
    chapters = BookChapterSerializer(source="book_chapters", many=True, read_only=True)

    class Meta:
        model = BookPart
        fields = ["id", "title", "order", "chapters"]


class BuildJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = BuildJob
        fields = [
            "celery_task_id",
            "started_at",
            "finished_at",
            "error_message",
        ]
        read_only_fields = fields


class BookSerializer(serializers.ModelSerializer):
    parts = BookPartSerializer(many=True, read_only=True)
    build_job = BuildJobSerializer(read_only=True)

    has_cover_image = serializers.SerializerMethodField()
    has_pdf = serializers.SerializerMethodField()
    has_html = serializers.SerializerMethodField()

    def get_has_cover_image(self, obj):
        return bool(obj.cover_image)

    def get_has_pdf(self, obj):
        return bool(getattr(obj, "build_job", None) and obj.build_job.pdf_path)

    def get_has_html(self, obj):
        return bool(obj.html_built_at and obj.html_path)

    class Meta:
        model = Book
        fields = [
            "id", "title", "doi", "status", "created_at", "updated_at",
            "parts", "build_job", "has_cover_image", "html_built_at",
            "has_pdf", "has_html", "last_build_format",
        ]
        read_only_fields = [
            "id", "status", "created_at", "updated_at", "parts",
            "build_job", "has_cover_image", "html_built_at",
            "has_pdf", "has_html", "last_build_format",
        ]


class BookListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view (no nested parts)."""

    has_pdf = serializers.SerializerMethodField()
    has_html = serializers.SerializerMethodField()

    def get_has_pdf(self, obj):
        return bool(getattr(obj, "build_job", None) and obj.build_job.pdf_path)

    def get_has_html(self, obj):
        return bool(obj.html_built_at and obj.html_path)

    class Meta:
        model = Book
        fields = [
            "id", "title", "doi", "status", "created_at", "updated_at",
            "html_built_at", "has_pdf", "has_html",
        ]
        read_only_fields = [
            "id", "status", "created_at", "updated_at", "html_built_at",
            "has_pdf", "has_html",
        ]
