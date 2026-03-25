from rest_framework import serializers

from .models import Chapter


class ChapterSerializer(serializers.ModelSerializer):
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
            "github_repo",
            "chapter_subdir",
            "cached_at",
        ]
        read_only_fields = fields
