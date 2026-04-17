"""Rebuild the full-text search index from existing HTML output."""

from django.core.management.base import BaseCommand

from catalog.models import Chapter
from catalog.search_index import reindex_chapter


class Command(BaseCommand):
    help = "Rebuild the full-text search index from existing chapter HTML."

    def add_arguments(self, parser):
        parser.add_argument("--chabbr", help="Reindex only this chapter")

    def handle(self, *args, **options):
        chabbr = options.get("chabbr")
        qs = Chapter.objects.filter(published=True, html_built_at__isnull=False)
        if chabbr:
            qs = qs.filter(chabbr=chabbr)

        total = 0
        for ch in qs:
            count = reindex_chapter(ch)
            if count:
                self.stdout.write(f"  {ch.chabbr}: {count} section(s)")
                total += count
            else:
                self.stdout.write(self.style.WARNING(f"  {ch.chabbr}: no HTML output, skipped"))

        self.stdout.write(self.style.SUCCESS(f"Indexed {total} total section(s)."))
