from pathlib import Path

from django.conf import settings
from rest_framework import serializers

from .models import Chapter, Discipline, Example, ExampleFigure, ExampleVersion


class DisciplineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discipline
        fields = ["id", "name", "slug", "color_primary"]
        read_only_fields = fields


class ChapterSerializer(serializers.ModelSerializer):
    discipline = DisciplineSerializer(read_only=True)
    has_pdf_labels = serializers.SerializerMethodField()
    examples_count = serializers.SerializerMethodField()

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

    def get_examples_count(self, obj):
        # The list/detail views annotate the queryset with this; if the
        # serializer is invoked on a Chapter instance pulled outside
        # those views (e.g. nested in another serializer), fall back to
        # a per-row count.
        annotated = getattr(obj, "examples_count_annotated", None)
        if annotated is not None:
            return annotated
        from .models import Example
        return (
            Example.objects.filter(
                status=Example.Status.PUBLISHED,
                chapters=obj,
            )
            .distinct()
            .count()
        )

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
            "related_to",
            "discipline",
            "github_repo",
            "chapter_subdir",
            "last_updated",
            "reviewer_name",
            "reviewed_at",
            "html_built_at",
            "cached_at",
            "has_pdf_labels",
            "examples_count",
        ]
        read_only_fields = fields


class ExampleFigureSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    def get_file_url(self, obj):
        # Routed through an authorized API endpoint rather than raw MEDIA;
        # nginx only proxies /api/, /admin/, and /static/.
        return f"/api/examples/{obj.example_id}/figures/{obj.id}/file"

    class Meta:
        model = ExampleFigure
        fields = [
            "id",
            "original_filename",
            "caption",
            "order",
            "file_url",
            "created_at",
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

    def get_author_display(self, obj) -> str:
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
    """Full detail — includes solution_tex.

    `preview_fresh` is True when the cached preview PDF was built after
    the example's last edit.
    `preview_pdf_url` is a short-lived signed URL that the iframe (or any
    "open in new tab" link) can use without carrying a JWT. PUBLISHED
    examples skip the token; everything else gets a fresh signature
    every time the detail is serialized (TTL 30 min).
    """
    primary_chapter = _ExampleChapterRefSerializer(read_only=True)
    chapters = _ExampleChapterRefSerializer(many=True, read_only=True)
    figures = ExampleFigureSerializer(many=True, read_only=True)
    author_display = serializers.SerializerMethodField()
    is_own = serializers.SerializerMethodField()
    preview_fresh = serializers.SerializerMethodField()
    preview_pdf_url = serializers.SerializerMethodField()

    def get_author_display(self, obj) -> str:
        return obj.author.full_name or "Anonymous"

    def get_is_own(self, obj):
        request = self.context.get("request")
        if request is None or not getattr(request, "user", None) or not request.user.is_authenticated:
            return False
        return obj.author_id == request.user.id

    def get_preview_fresh(self, obj):
        return (
            obj.preview_built_at is not None
            and obj.preview_built_at >= obj.updated_at
        )

    def get_preview_pdf_url(self, obj):
        if obj.preview_built_at is None:
            return None
        from .views import make_example_preview_token

        cache_bust = int(obj.preview_built_at.timestamp())
        url = f"/api/examples/{obj.id}/preview.pdf?v={cache_bust}"
        if obj.status != Example.Status.PUBLISHED:
            url += f"&t={make_example_preview_token(obj.id)}"
        return url

    class Meta:
        model = Example
        fields = [
            "id",
            "primary_chapter",
            "chapters",
            "figures",
            "statement_tex",
            "solution_tex",
            "difficulty",
            "license",
            "status",
            "rejection_reason",
            "author_display",
            "is_own",
            "preview_built_at",
            "preview_build_log",
            "preview_fresh",
            "preview_pdf_url",
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


class ExampleVersionSerializer(serializers.ModelSerializer):
    """A single row of the prior-state ledger for an Example.

    The full snapshot is exposed as a nested object so the frontend
    can render the historical content directly. `editor_display` is
    the best-effort attribution of who made the edit that *caused*
    this snapshot to be written (i.e. the author of version_no+1).
    """

    editor_display = serializers.SerializerMethodField()

    def get_editor_display(self, obj) -> str | None:
        if obj.created_by is None:
            return None
        return obj.created_by.full_name or "Anonymous"

    class Meta:
        model = ExampleVersion
        fields = [
            "version_no",
            "snapshot",
            "created_at",
            "editor_display",
        ]
        read_only_fields = fields
