"""
Management command: sync_chapters

Walks the src/ directory of the OpenChapters monorepo, reads chapter.json
from each subdirectory that contains one, and upserts the corresponding
Chapter records.

Usage::

    python manage.py sync_chapters
    python manage.py sync_chapters --repo OpenChapters/OpenChapters --src-path src
    python manage.py sync_chapters --dry-run

Subdirectories without a chapter.json are silently skipped (logged at DEBUG).
Called nightly by the ``catalog.tasks.sync_chapters_task`` Celery task.
"""

import logging
import re

from django.core.management.base import BaseCommand

# Patterns to validate chapter metadata used in subprocess calls.
_SAFE_PATH = re.compile(r"^[a-zA-Z0-9_/.+-]+$")
_SAFE_REPO = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")

from catalog.github_client import (
    DEFAULT_CHAPTERS_REPO,
    DEFAULT_SRC_PATH,
    fetch_chapter_json,
    list_chapter_subdirs,
    raw_file_url,
)
from catalog.models import Chapter, Discipline

logger = logging.getLogger(__name__)

# Subdirectory names to always skip (not real chapters)
_SKIP_DIRS = {"ChapterTemplate"}


class Command(BaseCommand):
    help = "Sync the chapter catalog from the OpenChapters monorepo on GitHub."

    def add_arguments(self, parser):
        parser.add_argument(
            "--repo",
            default=DEFAULT_CHAPTERS_REPO,
            help=f"GitHub repo (owner/name) containing the chapters (default: {DEFAULT_CHAPTERS_REPO})",
        )
        parser.add_argument(
            "--src-path",
            default=DEFAULT_SRC_PATH,
            help=f"Path within the repo where chapter subdirectories live (default: {DEFAULT_SRC_PATH})",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse chapter.json files but do not write to the database.",
        )

    def handle(self, *args, **options):
        repo: str = options["repo"]
        src_path: str = options["src_path"]
        dry_run: bool = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run mode — no database writes."))

        self.stdout.write(f"Listing chapter directories in {repo}/{src_path} …")
        try:
            subdirs = list_chapter_subdirs(repo, src_path)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Failed to list chapter directories: {exc}"))
            raise SystemExit(1)

        subdirs = [d for d in subdirs if d not in _SKIP_DIRS]
        self.stdout.write(f"Found {len(subdirs)} chapter director(ies). Syncing chapter.json …\n")

        # Determine the default branch once from the first repo response;
        # fall back to "master" which is what OpenChapters/OpenChapters uses.
        default_branch = "master"

        created = updated = skipped = errors = 0

        for dirname in subdirs:
            chapter_subdir = f"{src_path}/{dirname}"
            json_path = f"{chapter_subdir}/chapter.json"

            try:
                chapter_data = fetch_chapter_json(repo, json_path)
            except Exception as exc:
                self.stderr.write(
                    self.style.WARNING(f"  [{dirname}] fetch error: {exc}")
                )
                errors += 1
                continue

            if chapter_data is None:
                logger.debug("Skipping %s: no chapter.json", chapter_subdir)
                skipped += 1
                continue

            # Validate fields that flow into subprocess calls or file paths.
            entry_file = chapter_data.get("entry_file", "")
            if entry_file and not _SAFE_PATH.match(entry_file):
                self.stderr.write(
                    self.style.WARNING(f"  [{dirname}] unsafe entry_file: {entry_file!r}, skipping")
                )
                errors += 1
                continue
            if ".." in chapter_subdir or not _SAFE_PATH.match(chapter_subdir):
                self.stderr.write(
                    self.style.WARNING(f"  [{dirname}] unsafe chapter_subdir: {chapter_subdir!r}, skipping")
                )
                errors += 1
                continue

            # entry_file in chapter.json is relative to the chapter directory;
            # store the full path from the repo root in latex_entry_file.
            latex_entry_file = f"{chapter_subdir}/{entry_file}" if entry_file else ""

            # Build raw URL for the cover image (may not exist yet)
            cover_file = chapter_data.get("cover_image", "cover.png")
            cover_url = raw_file_url(repo, default_branch, f"{chapter_subdir}/{cover_file}")

            # Map discipline slug to Discipline object (if specified in chapter.json).
            # If not specified, don't overwrite an existing discipline assignment.
            discipline_slug = chapter_data.get("discipline", "")

            defaults = {
                "title": chapter_data.get("title", ""),
                "authors": chapter_data.get("authors", []),
                "description": chapter_data.get("description", ""),
                "toc": chapter_data.get("toc", []),
                "cover_image_url": cover_url,
                "latex_entry_file": latex_entry_file,
                "keywords": chapter_data.get("keywords", []),
                "chapter_type": chapter_data.get("chapter_type", "topical"),
                "chabbr": chapter_data.get("chabbr", ""),
                "author_urls": chapter_data.get("author_urls", {}),
                "depends_on": chapter_data.get("depends_on", []),
                "published": chapter_data.get("published", True),
            }
            if discipline_slug:
                discipline_obj = Discipline.objects.filter(slug=discipline_slug).first()
                if discipline_obj:
                    defaults["discipline"] = discipline_obj

            if dry_run:
                self.stdout.write(
                    f"  [dry-run] {chapter_subdir}: \"{chapter_data.get('title', '?')}\""
                )
                updated += 1
                continue

            _, was_created = Chapter.objects.update_or_create(
                github_repo=repo,
                chapter_subdir=chapter_subdir,
                defaults=defaults,
            )
            if was_created:
                created += 1
                self.stdout.write(f"  created  {chapter_subdir}")
            else:
                updated += 1
                self.stdout.write(f"  updated  {chapter_subdir}")

        label = "dry-run" if dry_run else "done"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{label}: created={created} updated={updated} "
                f"skipped={skipped} errors={errors}"
            )
        )
