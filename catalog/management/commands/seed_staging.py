"""Seed a freshly-migrated staging database with the minimum content
needed to click through the app:

  - an admin user (staff + superuser)
  - a regular author user
  - one Discipline, one Chapter (published, no real chabbr / repo)
  - one draft Example owned by the author user

Idempotent: every object is fetched-or-created by a stable natural key,
so running the command twice is a no-op.

Usage:
    docker compose -p ocweb_staging -f docker-compose.staging.yml \\
        exec web python manage.py seed_staging
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Chapter, Discipline, Example
from users.models import User


ADMIN_EMAIL = "admin@staging.local"
AUTHOR_EMAIL = "author@staging.local"
DEFAULT_PASSWORD = "staging-password"


class Command(BaseCommand):
    help = "Seed the staging database with a baseline admin, author, chapter and example."

    @transaction.atomic
    def handle(self, *args, **options):
        admin, admin_created = User.objects.get_or_create(
            email=ADMIN_EMAIL,
            defaults={
                "full_name": "Staging Admin",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        if admin_created:
            admin.set_password(DEFAULT_PASSWORD)
            admin.save()
            self.stdout.write(self.style.SUCCESS(f"  created admin: {ADMIN_EMAIL}"))
        else:
            self.stdout.write(f"  admin already present: {ADMIN_EMAIL}")

        author, author_created = User.objects.get_or_create(
            email=AUTHOR_EMAIL,
            defaults={"full_name": "Staging Author", "is_active": True},
        )
        if author_created:
            author.set_password(DEFAULT_PASSWORD)
            author.save()
            self.stdout.write(self.style.SUCCESS(f"  created author: {AUTHOR_EMAIL}"))
        else:
            self.stdout.write(f"  author already present: {AUTHOR_EMAIL}")

        discipline, _ = Discipline.objects.get_or_create(
            slug="staging-discipline",
            defaults={"name": "Staging Discipline", "color_primary": "#6b7280"},
        )

        chapter, chapter_created = Chapter.objects.get_or_create(
            chabbr="STG",
            defaults={
                "title": "Staging Sample Chapter",
                "authors": ["Staging Author"],
                "description": "Placeholder chapter for clicking through staging.",
                "chapter_type": Chapter.ChapterType.TOPICAL,
                "discipline": discipline,
                "published": True,
                "github_repo": "OpenChapters/staging-placeholder",
                "chapter_subdir": "",
            },
        )
        if chapter_created:
            self.stdout.write(self.style.SUCCESS("  created chapter: STG"))

        example, example_created = Example.objects.get_or_create(
            statement_tex="What is $1 + 1$?",
            defaults={
                "author": author,
                "primary_chapter": chapter,
                "solution_tex": "By definition, $1 + 1 = 2$.",
                "difficulty": Example.Difficulty.INTRODUCTORY,
                "status": Example.Status.DRAFT,
            },
        )
        if example_created:
            example.chapters.add(chapter)
            self.stdout.write(self.style.SUCCESS("  created example #%d" % example.id))

        self.stdout.write(self.style.SUCCESS("Done."))
        self.stdout.write(f"  admin login : {ADMIN_EMAIL} / {DEFAULT_PASSWORD}")
        self.stdout.write(f"  author login: {AUTHOR_EMAIL} / {DEFAULT_PASSWORD}")
