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

    class Meta:
        model = Book
        fields = ["id", "title", "status", "created_at", "updated_at", "parts", "build_job"]
        read_only_fields = ["id", "status", "created_at", "updated_at", "parts", "build_job"]


class BookListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view (no nested parts)."""

    class Meta:
        model = Book
        fields = ["id", "title", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "status", "created_at", "updated_at"]
