"""
Management command: reset_catalog

Wipes all catalog content (chapters + worked examples) and every
user-assembled book and frozen snapshot, returning the database to a clean,
freshly-syncable state — WITHOUT touching user accounts, disciplines, site
configuration, or the audit log.

Intended for the testing-phase reset described in todo.txt: after chapters
have been consolidated and re-pushed to the OpenChapters monorepo, run this,
then re-run ``sync_chapters`` to repopulate the catalog from scratch.

Deletes (in FK-safe order — PROTECT FKs from BookChapter/Example into
Chapter, and Example.author into User, force books and examples to go first)::

    books.Book        -> cascades BookPart, BookChapter, BuildJob, BuildStep
    books.FrozenBook  -- survives Book deletion via SET_NULL, so deleted here
    catalog.Example   -> cascades ExampleFigure, ExampleVersion
    catalog.Chapter   -> cascades ChapterSearchIndex

Preserves::

    users.User and all sessions
    catalog.Discipline  -- taxonomy; NOT recreated by sync_chapters (it only
                           maps existing slugs), so deleting it would orphan
                           every re-synced chapter. Kept deliberately.
    admin_api.SiteConfig / SiteSetting / AuditEntry

Also clears the on-disk build/upload artifacts under MEDIA_ROOT that those
rows referenced (book PDFs, per-book HTML, frozen snapshots, example figures
and previews, per-chapter HTML, foundational label PDFs, book covers). Pass
``--keep-media`` to delete database rows only. The warm git clone cache lives
on a worker-only volume and is cleared by the wrapper script, not here.

Usage::

    python manage.py reset_catalog --dry-run
    python manage.py reset_catalog
    python manage.py reset_catalog --keep-media
"""

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from books.models import Book, FrozenBook
from catalog.models import Chapter, Discipline, Example


class Command(BaseCommand):
    help = (
        "Wipe all chapters, examples, books and frozen snapshots (keeping user "
        "accounts, disciplines and site config), restoring a clean pre-sync state."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without writing to the database or touching files.",
        )
        parser.add_argument(
            "--keep-media",
            action="store_true",
            help="Delete database rows only; leave on-disk media artifacts in place.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        keep_media: bool = options["keep_media"]

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run — no rows deleted, no files removed.\n"))

        # Count up-front; the cascades make post-hoc counting unreliable.
        counts = {
            "books.Book": Book.objects.count(),
            "books.FrozenBook": FrozenBook.objects.count(),
            "catalog.Example": Example.objects.count(),
            "catalog.Chapter": Chapter.objects.count(),
        }
        self.stdout.write("Content to delete:")
        for label, n in counts.items():
            self.stdout.write(f"  {label:<20} {n}")
        self.stdout.write(
            f"\nPreserving: {Discipline.objects.count()} discipline(s), "
            "all user accounts, sessions, site config and audit log.\n"
        )

        if not dry_run:
            with transaction.atomic():
                # Order matters (see module docstring).
                Book.objects.all().delete()        # cascades parts, book-chapters, jobs, steps
                FrozenBook.objects.all().delete()  # SET_NULL survivor — clear explicitly
                Example.objects.all().delete()     # cascades figures, versions
                Chapter.objects.all().delete()     # cascades search index
            self.stdout.write(self.style.SUCCESS("Database rows deleted."))

        # ── On-disk artifacts ────────────────────────────────────────────────
        media = Path(settings.MEDIA_ROOT)
        targets = [
            Path(settings.BUILD_OUTPUT_DIR),       # generated book PDFs
            Path(settings.BUILD_HTML_OUTPUT_DIR),  # per-book lwarp HTML
            Path(settings.BUILD_EPUB_OUTPUT_DIR),  # per-book EPUB
            Path(settings.FROZEN_OUTPUT_DIR),      # frozen snapshots
            media / "covers",                      # book cover uploads
            media / "example_figures",             # example figure uploads
            media / "examples",                    # example preview PDFs
            media / "html",                        # per-chapter HTML
            media / "pdf_labels",                  # foundational label PDFs
        ]
        if keep_media:
            self.stdout.write("Keeping on-disk media (--keep-media).")
        else:
            self.stdout.write("\nClearing on-disk artifacts:")
            for d in targets:
                removed = self._clear_dir_contents(d, dry_run)
                verb = "would remove" if dry_run else "removed"
                self.stdout.write(f"  {verb} {removed:>4} item(s)  {d}")

        label = "dry-run complete" if dry_run else "reset complete"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{label}. Next: run `python manage.py sync_chapters` to repopulate the catalog."
            )
        )

    @staticmethod
    def _clear_dir_contents(directory: Path, dry_run: bool) -> int:
        """Remove every child of *directory* (files and subdirs), keeping the
        directory itself so a mounted volume's mount-point survives. Returns
        the number of top-level entries removed (or that would be removed)."""
        if not directory.is_dir():
            return 0
        count = 0
        for child in directory.iterdir():
            count += 1
            if dry_run:
                continue
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except OSError:
                    pass
        return count
