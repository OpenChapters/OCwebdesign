from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import ValidationError
from django.db import models


def _validate_string_list(value):
    """Validate that a JSONField contains a list of strings."""
    if not isinstance(value, list):
        raise ValidationError("Must be a list.")
    for item in value:
        if not isinstance(item, str):
            raise ValidationError(f"All items must be strings, got {type(item).__name__}.")


class Discipline(models.Model):
    """
    A discipline or subject area (e.g., Materials Science, Mechanical Engineering).

    Each discipline has its own GitHub repo containing chapters, and can
    optionally define custom LaTeX styling and cover templates.
    """

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    # GitHub source for this discipline's chapters
    github_repo = models.CharField(max_length=200)
    github_src_path = models.CharField(max_length=200, default="src")

    # Optional discipline-specific styling
    color_primary = models.CharField(max_length=7, default="#2563eb")

    # Display order on the Browse page
    order = models.PositiveIntegerField(default=0)
    published = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Chapter(models.Model):
    """
    A single chapter available in the OpenChapters catalog.

    Records are populated (and refreshed) by the sync_chapters management
    command, which reads chapter.json from each chapter repo in the
    OpenChapters GitHub organization.
    """

    class ChapterType(models.TextChoices):
        FOUNDATIONAL = "foundational", "Foundational"
        TOPICAL = "topical", "Topical"

    # GitHub repo identifier, e.g. "OpenChapters/OpenChapters"
    github_repo = models.CharField(max_length=200)

    # Path to the chapter's subdirectory within the repo, e.g. "src/LinearAlgebra"
    # Together with github_repo this uniquely identifies a chapter.
    chapter_subdir = models.CharField(max_length=200, default="")

    title = models.CharField(max_length=300)
    authors = models.JSONField(default=list, validators=[_validate_string_list])
    description = models.TextField(blank=True)

    # List of section headings from chapter.json, shown in TOC hover preview
    toc = models.JSONField(default=list, validators=[_validate_string_list])

    # Raw GitHub URL for cover image, served directly to the browser
    cover_image_url = models.URLField(blank=True)

    # Full path to the LaTeX entry file from the repo root,
    # e.g. "src/LinearAlgebra/LinearAlgebra.tex"
    latex_entry_file = models.CharField(max_length=200)

    keywords = models.JSONField(default=list, validators=[_validate_string_list])

    # Mapping of author name → homepage URL, e.g. {"Marc De Graef": "https://..."}
    author_urls = models.JSONField(default=dict, blank=True)

    chapter_type = models.CharField(
        max_length=20,
        choices=ChapterType.choices,
        default=ChapterType.TOPICAL,
    )

    # Unique chapter abbreviation used in \label and \ref, e.g. "LINALG"
    chabbr = models.CharField(max_length=20, blank=True)

    # List of chabbr values for foundational chapters this chapter cross-references.
    # Used by the frontend to auto-include required foundational chapters.
    depends_on = models.JSONField(default=list, validators=[_validate_string_list])

    # False for template/placeholder chapters not ready for inclusion in builds.
    published = models.BooleanField(default=True)

    # Discipline this chapter belongs to (nullable for backwards compatibility)
    discipline = models.ForeignKey(
        Discipline,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chapters",
    )

    # Date of the most recent commit touching this chapter's subdirectory
    last_updated = models.DateTimeField(null=True, blank=True)

    # Review information (entered manually by an admin)
    reviewer_name = models.CharField(max_length=200, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Timestamp of the last successful HTML build via lwarp
    html_built_at = models.DateTimeField(null=True, blank=True)

    # Timestamp of the last successful sync from GitHub
    cached_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(
                fields=["github_repo", "chapter_subdir"],
                name="unique_chapter_in_repo",
            )
        ]

    def __str__(self):
        return self.title

    @property
    def repo_dirname(self):
        """Local directory name when the repo is cloned, e.g. 'OpenChapters'."""
        return self.github_repo.split("/")[-1]


class ChapterSearchIndex(models.Model):
    """Full-text search entry for a section within a chapter's HTML output.

    Populated after each successful HTML build by parsing the generated
    node-*.html files and splitting them by section heading. The
    search_vector is maintained by a triggered UPDATE in the indexing
    code and queried via Django's SearchRank.
    """

    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="search_entries"
    )
    # Heading text of the section ("1.2 Complex number representation"),
    # empty string for content before the first heading.
    section_title = models.CharField(max_length=500, blank=True)
    # Filename of the HTML node containing this section (e.g., "node-1.html").
    html_node = models.CharField(max_length=100)
    # Anchor within the node (e.g., "autosec-9"); empty for top of file.
    anchor = models.CharField(max_length=200, blank=True)
    # Plain-text content of the section (HTML stripped).
    text_content = models.TextField()
    # PostgreSQL tsvector for fast ranked search.
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta:
        indexes = [
            GinIndex(fields=["search_vector"]),
            models.Index(fields=["chapter"]),
        ]

    def __str__(self):
        return f"{self.chapter.chabbr}: {self.section_title or '(intro)'}"
