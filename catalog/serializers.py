from rest_framework import serializers

from .models import Chapter, Discipline


class DisciplineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discipline
        fields = ["id", "name", "slug", "color_primary"]
        read_only_fields = fields


class ChapterSerializer(serializers.ModelSerializer):
    discipline = DisciplineSerializer(read_only=True)

    class Meta:
        model = Chapter
        fields = [
            "id",
            "title",
            "authors",
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
            "cached_at",
        ]
        read_only_fields = fields
