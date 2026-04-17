"""Index a chapter's generated HTML for full-text search.

After a successful lwarp build, parse the generated node-*.html files,
split them by section heading, and populate ChapterSearchIndex rows.
PostgreSQL's tsvector/SearchRank powers the search endpoint.
"""

import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.postgres.search import SearchVector
from django.db import transaction

from .models import Chapter, ChapterSearchIndex

logger = logging.getLogger(__name__)

HTML_DIR = Path(settings.BASE_DIR) / "media" / "html"

# Headings that start a new indexed section.
HEADING_TAGS = ("h1", "h2", "h3", "h4")


def _clean_text(s: str) -> str:
    """Collapse whitespace and strip MathJax macro clutter."""
    s = re.sub(r"\s+", " ", s).strip()
    # MathJax fills the page with \(...\) definitions; strip LaTeX-looking tokens
    s = re.sub(r"\\[a-zA-Z@]+\*?", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_sections(html_path: Path):
    """Yield (section_title, anchor, text_content) tuples from one HTML file.

    The textbody section of each lwarp page is split at each heading tag.
    Text before the first heading becomes the intro entry (empty title).
    """
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")

    # lwarp wraps content in <section class="textbody">. Fall back to body
    # if not found (e.g., for index.html which has no textbody).
    body = soup.find("section", class_="textbody") or soup.body
    if body is None:
        return

    # Remove script, style, nav, header, and the MathJax customization block
    for tag in body.find_all(["script", "style", "nav", "header"]):
        tag.decompose()
    for tag in body.find_all(attrs={"data-nosnippet": True}):
        tag.decompose()

    current_title = ""
    current_anchor = ""
    buffer = []

    for element in body.descendants:
        if getattr(element, "name", None) in HEADING_TAGS:
            # Flush the previous section
            text = _clean_text(" ".join(buffer))
            if text:
                yield current_title, current_anchor, text

            current_title = element.get_text(" ", strip=True)
            # Try to find an anchor — either the heading's id or a preceding <a id="...">
            anchor = element.get("id", "") or ""
            if not anchor:
                prev = element.find_previous(
                    lambda t: t.name == "a" and t.get("id", "").startswith("auto")
                )
                if prev:
                    anchor = prev["id"]
            current_anchor = anchor
            buffer = []
        elif isinstance(element, str):
            # Only collect text from leaf string nodes
            parent_name = element.parent.name if element.parent else ""
            if parent_name in ("script", "style"):
                continue
            buffer.append(str(element))

    # Flush the final section
    text = _clean_text(" ".join(buffer))
    if text:
        yield current_title, current_anchor, text


def reindex_chapter(chapter: Chapter) -> int:
    """Rebuild the search index for one chapter's HTML output.

    Deletes any existing entries for the chapter, parses all node-*.html
    files, and creates fresh entries. Returns the number of entries
    created. If no HTML output exists, returns 0 without modifying anything.
    """
    if not chapter.chabbr:
        return 0

    chapter_dir = HTML_DIR / chapter.chabbr
    if not chapter_dir.is_dir():
        return 0

    # Collect (section_title, node, anchor, text) for every section in every node
    entries = []
    for html_path in sorted(chapter_dir.glob("node-*.html")):
        for title, anchor, text in _extract_sections(html_path):
            # Ignore sections with very little text (boilerplate)
            if len(text) < 40:
                continue
            entries.append({
                "section_title": title[:500],
                "html_node": html_path.name,
                "anchor": anchor[:200],
                "text_content": text,
            })

    with transaction.atomic():
        ChapterSearchIndex.objects.filter(chapter=chapter).delete()
        rows = [
            ChapterSearchIndex(chapter=chapter, **e) for e in entries
        ]
        ChapterSearchIndex.objects.bulk_create(rows)

        # Compute search_vector for the new rows. Weight the section
        # title higher than the body text.
        ChapterSearchIndex.objects.filter(chapter=chapter).update(
            search_vector=(
                SearchVector("section_title", weight="A", config="english")
                + SearchVector("text_content", weight="B", config="english")
            )
        )

    logger.info("Indexed %d section(s) for chapter %s", len(entries), chapter.chabbr)
    return len(entries)
