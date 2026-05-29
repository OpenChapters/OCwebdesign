from django.contrib.auth import get_user_model
from rest_framework import serializers

from catalog.models import Chapter, Discipline

User = get_user_model()


class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "password", "is_staff"]

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            is_staff=validated_data.get("is_staff", False),
        )


class AdminUserListSerializer(serializers.ModelSerializer):
    book_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "is_active", "is_staff", "is_superuser",
            "date_joined", "last_login", "book_count",
        ]
        read_only_fields = fields


class AdminUserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "is_active", "is_staff", "is_superuser",
            "date_joined", "last_login",
        ]
        read_only_fields = ["id", "email", "date_joined", "last_login"]


class AdminDisciplineSerializer(serializers.ModelSerializer):
    chapter_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Discipline
        fields = [
            "id", "name", "slug", "description", "github_repo",
            "github_src_path", "color_primary", "order", "published",
            "chapter_count",
        ]
        read_only_fields = ["id", "chapter_count"]


class AdminChapterSerializer(serializers.ModelSerializer):
    discipline_name = serializers.CharField(source="discipline.name", read_only=True, default="")
    examples_count = serializers.SerializerMethodField()
    github_edit_url = serializers.SerializerMethodField()

    def get_examples_count(self, obj):
        # Falls back to a per-row query if the queryset wasn't annotated
        # (e.g. detail views that don't go through AdminChapterListView).
        annotated = getattr(obj, "examples_count_annotated", None)
        if annotated is not None:
            return annotated
        from catalog.models import Example
        return (
            Example.objects.filter(
                status=Example.Status.PUBLISHED,
                chapters=obj,
            )
            .distinct()
            .count()
        )

    def get_github_edit_url(self, obj) -> str:
        from django.conf import settings
        branch = getattr(settings, "OPENCHAPTERS_DEFAULT_BRANCH", "master")
        return f"https://github.com/{obj.github_repo}/edit/{branch}/{obj.chapter_subdir}/chapter.json"

    class Meta:
        model = Chapter
        # Everything that lives in chapter.json (title, authors, description,
        # keywords, toc, depends_on, chabbr, chapter_type, cover_image_url,
        # discipline) is read-only here — those edits belong on GitHub via a
        # PR against the monorepo. Only the admin-curation trio is writable.
        fields = [
            "id", "title", "authors", "description", "toc",
            "cover_image_url", "keywords", "chapter_type", "chabbr",
            "depends_on", "published", "discipline", "discipline_name",
            "github_repo", "chapter_subdir", "latex_entry_file",
            "reviewer_name", "reviewed_at", "html_built_at", "cached_at",
            "examples_count", "github_edit_url",
        ]
        read_only_fields = [
            "id", "title", "authors", "description", "toc",
            "cover_image_url", "keywords", "chapter_type", "chabbr",
            "depends_on", "discipline", "discipline_name",
            "github_repo", "chapter_subdir", "latex_entry_file",
            "html_built_at", "cached_at", "examples_count", "github_edit_url",
        ]
