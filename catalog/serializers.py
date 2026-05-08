from pathlib import Path

from django.conf import settings
from rest_framework import serializers

from .models import Chapter, Discipline, Example


class DisciplineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discipline
        fields = ["id", "name", "slug", "color_primary"]
        read_only_fields = fields


class ChapterSerializer(serializers.ModelSerializer):
    discipline = DisciplineSerializer(read_only=True)
    has_pdf_labels = serializers.SerializerMethodField()

    def get_has_pdf_labels(self, obj):
        # Foundational-only artifact; the labels-PDF is built nightly
        # and surfaced via /api/chapters/<id>/pdf-labels/.
        if (
            obj.chapter_type != Chapter.ChapterType.FOUNDATIONAL
            or not obj.chabbr
        ):
            return False
        return (
            Path(settings.BASE_DIR) / "media" / "pdf_labels" / f"{obj.chabbr}.pdf"
        ).is_file()

    class Meta:
        model = Chapter
        fields = [
            "id",
            "title",
            "authors",
            "author_urls",
            "description",
            "toc",
            "cover_image_url",
            "keywords",
            "chapter_type",
            "chabbr",
            "depends_on",
            "discipline",
            "github_repo",
            "chapter_subdir",
            "last_updated",
            "reviewer_name",
            "reviewed_at",
            "html_built_at",
            "cached_at",
            "has_pdf_labels",
        ]
        read_only_fields = fields


class _ExampleChapterRefSerializer(serializers.ModelSerializer):
    """Compact chapter ref nested inside Example payloads."""
    class Meta:
        model = Chapter
        fields = ["id", "title", "chabbr"]
        read_only_fields = fields


class ExampleListSerializer(serializers.ModelSerializer):
    """List view — omits solution_tex to keep payloads small."""
    primary_chapter = _ExampleChapterRefSerializer(read_only=True)
    chapters = _ExampleChapterRefSerializer(many=True, read_only=True)
    author_display = serializers.SerializerMethodField()

    def get_author_display(self, obj):
        return obj.author.full_name or "Anonymous"

    class Meta:
        model = Example
        fields = [
            "id",
            "primary_chapter",
            "chapters",
            "statement_tex",
            "difficulty",
            "status",
            "author_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ExampleDetailSerializer(serializers.ModelSerializer):
    """Full detail — includes solution_tex."""
    primary_chapter = _ExampleChapterRefSerializer(read_only=True)
    chapters = _ExampleChapterRefSerializer(many=True, read_only=True)
    author_display = serializers.SerializerMethodField()

    def get_author_display(self, obj):
        return obj.author.full_name or "Anonymous"

    class Meta:
        model = Example
        fields = [
            "id",
            "primary_chapter",
            "chapters",
            "statement_tex",
            "solution_tex",
            "difficulty",
            "license",
            "status",
            "rejection_reason",
            "author_display",
            "preview_built_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ExampleWriteSerializer(serializers.ModelSerializer):
    """Author-side write serializer for create / update.

    Validates: at least one chapter, primary_chapter ∈ chapters.
    """
    chapters = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Chapter.objects.filter(published=True),
    )
    primary_chapter = serializers.PrimaryKeyRelatedField(
        queryset=Chapter.objects.filter(published=True),
    )

    class Meta:
        model = Example
        fields = [
            "id",
            "primary_chapter",
            "chapters",
            "statement_tex",
            "solution_tex",
            "difficulty",
        ]
        read_only_fields = ["id"]

    def validate(self, data):
        # `chapters` may be absent on PATCH; fall back to current value.
        chapters = data.get("chapters")
        if chapters is None and self.instance is not None:
            chapters = list(self.instance.chapters.all())
        if not chapters:
            raise serializers.ValidationError(
                {"chapters": "At least one chapter must be tagged."}
            )

        primary = data.get("primary_chapter")
        if primary is None and self.instance is not None:
            primary = self.instance.primary_chapter
        if primary is None:
            raise serializers.ValidationError(
                {"primary_chapter": "A primary chapter is required."}
            )

        if primary not in chapters:
            raise serializers.ValidationError(
                {"primary_chapter": "Primary chapter must be one of the tagged chapters."}
            )

        for field in ("statement_tex", "solution_tex"):
            value = data.get(field)
            if value is None and self.instance is not None:
                value = getattr(self.instance, field)
            if not value or not value.strip():
                raise serializers.ValidationError({field: "This field cannot be empty."})

        return data
