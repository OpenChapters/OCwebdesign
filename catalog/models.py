from django.conf import settings
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


class Example(models.Model):
    """
    A worked example: a LaTeX problem statement plus its solution,
    tagged to one or more chapters. Authors submit drafts; an admin
    reviews and publishes. Published examples appear on the public
    /examples browse page, on each tagged chapter's detail page, and
    can be appended at book build time per the include_examples /
    include_solutions flags on the build.
    """

    class Difficulty(models.TextChoices):
        INTRODUCTORY = "introductory", "Introductory"
        STANDARD = "standard", "Standard"
        ADVANCED = "advanced", "Advanced"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending review"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="examples",
    )

    # All chapters this example is relevant to (M2M).
    chapters = models.ManyToManyField(
        Chapter,
        related_name="examples",
    )

    # The chapter whose preamble drives the snippet compile in Phase 2.
    # Must be one of `chapters` (validated in the serializer, since M2M
    # values aren't available at model.clean() time before save).
    primary_chapter = models.ForeignKey(
        Chapter,
        on_delete=models.PROTECT,
        related_name="primary_examples",
    )

    # Optional stable identifier for idempotent batch re-imports. Scoped
    # per-author so two authors can use the same slug independently.
    # NULL when the example was created via the regular editor.
    slug = models.CharField(max_length=64, null=True, blank=True)

    statement_tex = models.TextField()
    solution_tex = models.TextField()

    difficulty = models.CharField(
        max_length=16,
        choices=Difficulty.choices,
        default=Difficulty.STANDARD,
    )

    license = models.CharField(max_length=64, default="CC BY-NC-SA 4.0")

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    rejection_reason = models.TextField(blank=True)

    # Set when the snippet preview compile succeeds (Phase 2).
    preview_built_at = models.DateTimeField(null=True, blank=True)
    preview_build_log = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["status", "primary_chapter"]),
        ]
        constraints = [
            # Per-author slug uniqueness (NULL slugs are excluded so the
            # vast majority of editor-created rows aren't constrained).
            models.UniqueConstraint(
                fields=["author", "slug"],
                condition=models.Q(slug__isnull=False),
                name="unique_example_slug_per_author",
            ),
        ]

    def __str__(self):
        return f"Example #{self.pk} ({self.get_status_display()})"


def _example_figure_upload_to(instance, filename):
    return f"example_figures/{instance.example_id}/{filename}"


class ExampleFigure(models.Model):
    """
    A figure attached to a worked example. The file is referenced from
    the example's LaTeX source as \\includegraphics{filename} (no path)
    — the build pipeline copies the file into the build dir and emits a
    per-example \\graphicspath so the reference resolves cleanly without
    filename collisions across examples.
    """

    ALLOWED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".eps")
    MAX_BYTES = 5 * 1024 * 1024

    example = models.ForeignKey(
        Example,
        on_delete=models.CASCADE,
        related_name="figures",
    )
    file = models.FileField(upload_to=_example_figure_upload_to)
    # Original filename as referenced from the LaTeX source. Stored
    # separately because Django may suffix uploaded files when names
    # collide; \includegraphics{...} must match the actual on-disk name
    # we copy into the build dir.
    original_filename = models.CharField(max_length=255)
    caption = models.CharField(max_length=500, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["example_id", "order", "id"]
        indexes = [
            models.Index(fields=["example"]),
        ]

    def __str__(self):
        return f"Figure {self.original_filename} for Example #{self.example_id}"


class ExampleVersion(models.Model):
    """
    Append-only ledger of prior `Example` content states.

    A row is written by a pre_save signal whenever a tracked content
    field on `Example` is about to change. The snapshot captures the
    *prior* state so the live row stays canonical and the ledger gives
    you point-in-time recovery and an edit history.

    The snapshot is stored as a JSON blob (rather than mirrored columns)
    so the schema doesn't need to migrate every time we add a new
    example field — and so a chapter row being deleted doesn't break a
    foreign key into the ledger.
    """

    example = models.ForeignKey(
        Example,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    # Monotonically increasing per-example counter (1, 2, 3, ...).
    version_no = models.PositiveIntegerField()
    # JSON shape: {
    #   "statement_tex": str, "solution_tex": str, "difficulty": str,
    #   "primary_chapter_chabbr": str | None,
    #   "chapters_chabbrs": [str, ...],
    #   "status": str, "slug": str | None,
    # }
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    # Best-effort attribution. Authenticated views set this via the
    # signal helper; nullable so a management-command save still works.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["example_id", "version_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["example", "version_no"],
                name="unique_example_version_no",
            ),
        ]
        indexes = [
            models.Index(fields=["example", "-version_no"]),
        ]

    def __str__(self):
        return f"Example #{self.example_id} v{self.version_no}"
