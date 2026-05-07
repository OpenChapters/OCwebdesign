from pathlib import Path

from django.conf import settings
from rest_framework import serializers

from .models import Chapter, Discipline


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
