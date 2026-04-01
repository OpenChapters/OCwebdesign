from django.contrib.auth import get_user_model
from rest_framework import serializers

from catalog.models import Chapter

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


class AdminChapterSerializer(serializers.ModelSerializer):
    discipline_name = serializers.CharField(source="discipline.name", read_only=True, default="")

    class Meta:
        model = Chapter
        fields = [
            "id", "title", "authors", "description", "toc",
            "cover_image_url", "keywords", "chapter_type", "chabbr",
            "depends_on", "published", "discipline", "discipline_name",
            "github_repo", "chapter_subdir", "latex_entry_file", "cached_at",
        ]
        read_only_fields = [
            "id", "github_repo", "chapter_subdir", "latex_entry_file",
            "cached_at", "discipline_name",
        ]
