from catalog.models import Chapter
from catalog.serializers import ChapterSerializer
from rest_framework import serializers

from .models import Book, BookChapter, BookPart, BuildJob, BuildStep


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


class BuildStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = BuildStep
        fields = [
            "name",
            "label",
            "order",
            "status",
            "detail",
            "started_at",
            "finished_at",
            "log_tail",
        ]
        read_only_fields = fields


class BuildJobSerializer(serializers.ModelSerializer):
    steps = BuildStepSerializer(many=True, read_only=True)

    class Meta:
        model = BuildJob
        fields = [
            "celery_task_id",
            "started_at",
            "finished_at",
            "error_message",
            "steps",
        ]
        read_only_fields = fields


class BookSerializer(serializers.ModelSerializer):
    parts = BookPartSerializer(many=True, read_only=True)
    build_job = BuildJobSerializer(read_only=True)

    has_cover_image = serializers.SerializerMethodField()
    has_pdf = serializers.SerializerMethodField()
    has_html = serializers.SerializerMethodField()
    examples_count = serializers.SerializerMethodField()

    def get_has_cover_image(self, obj):
        return bool(obj.cover_image)

    def get_has_pdf(self, obj):
        return bool(getattr(obj, "build_job", None) and obj.build_job.pdf_path)

    def get_has_html(self, obj):
        return bool(obj.html_built_at and obj.html_path)

    def get_examples_count(self, obj):
        # Distinct PUBLISHED Examples tagged to any chapter in the book.
        # Each renders exactly once at build time (earliest-in-book host),
        # so this also matches what will actually appear in the artifact.
        from catalog.models import Example

        chapter_ids = list(
            obj.parts.values_list("book_chapters__chapter_id", flat=True).distinct()
        )
        if not chapter_ids:
            return 0
        return (
            Example.objects.filter(
                status=Example.Status.PUBLISHED,
                chapters__in=chapter_ids,
            )
            .distinct()
            .count()
        )

    class Meta:
        model = Book
        fields = [
            "id", "title", "doi", "status", "created_at", "updated_at",
            "parts", "build_job", "has_cover_image", "html_built_at",
            "has_pdf", "has_html", "last_build_format",
            "include_examples", "include_solutions", "examples_count",
            "excluded_example_ids",
        ]
        read_only_fields = [
            "id", "status", "created_at", "updated_at", "parts",
            "build_job", "has_cover_image", "html_built_at",
            "has_pdf", "has_html", "last_build_format", "examples_count",
        ]

    def validate_excluded_example_ids(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Must be a list of example ids.")
        ids = []
        for v in value:
            if not isinstance(v, int) or isinstance(v, bool):
                raise serializers.ValidationError("All entries must be integers.")
            ids.append(v)
        # de-dup, preserve order
        seen = set()
        return [i for i in ids if not (i in seen or seen.add(i))]


class PublicChapterRefSerializer(serializers.ModelSerializer):
    """Minimal chapter info shown in community library entries."""

    class Meta:
        model = Chapter
        fields = ["id", "title", "chabbr"]
        read_only_fields = fields


class PublicBookPartSerializer(serializers.ModelSerializer):
    chapters = serializers.SerializerMethodField()

    def get_chapters(self, obj):
        chapters = [bc.chapter for bc in obj.book_chapters.all()]
        return PublicChapterRefSerializer(chapters, many=True).data

    class Meta:
        model = BookPart
        fields = ["title", "order", "chapters"]
        read_only_fields = fields


class PublicBookSerializer(serializers.ModelSerializer):
    """Slim, no-attribution-by-default book payload for the community page.

    Excludes any user-identifying field except a display name (full_name
    falls back to "Anonymous" when blank). No build artifacts are exposed
    — community sharing is listing-only in this phase.
    """

    parts = PublicBookPartSerializer(many=True, read_only=True)
    author_display = serializers.SerializerMethodField()

    def get_author_display(self, obj):
        name = (obj.user.full_name or "").strip()
        return name or "Anonymous"

    class Meta:
        model = Book
        fields = ["id", "title", "author_display", "updated_at", "parts"]
        read_only_fields = fields


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
