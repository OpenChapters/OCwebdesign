from django.conf import settings
from django.db import models


class Book(models.Model):
    """A user's custom book assembly, composed of parts and chapters."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        BUILDING = "building", "Building"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="books",
    )
    title = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    def _cover_upload_path(instance, filename):
        return f"covers/user_{instance.user_id}/{filename}"

    cover_image = models.FileField(
        upload_to=_cover_upload_path,
        blank=True,
        help_text="Optional cover page PDF (A4, two 298pt-high images separated by white).",
    )
    doi = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional DOI link for this book.",
    )

    # Per-book HTML build artifacts (lwarp)
    html_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Filesystem path to the directory containing the built HTML output.",
    )
    html_built_at = models.DateTimeField(null=True, blank=True)

    class BuildFormat(models.TextChoices):
        PDF = "pdf", "PDF"
        HTML = "html", "HTML"
        BOTH = "both", "PDF + HTML"
        # EPUB and ALL are kept in the schema so the backend pipeline
        # remains wired, but they are not surfaced in the 1.2 UI because
        # tex4ebook cannot handle the OpenChapters preamble cleanly yet.
        EPUB = "epub", "EPUB (experimental)"
        ALL = "all", "All formats (PDF + HTML + EPUB, experimental)"

    last_build_format = models.CharField(
        max_length=8,
        choices=BuildFormat.choices,
        default=BuildFormat.PDF,
        help_text="Format selected for the most recent build; used by Retry.",
    )

    # Per-book EPUB build artifact (tex4ebook)
    epub_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Filesystem path to the most recent EPUB output.",
    )
    epub_built_at = models.DateTimeField(null=True, blank=True)

    # ── Worked-examples integration (todo #5 Phase 3) ────────────────────────
    # When include_examples is True, the build pipeline appends a "Worked
    # Examples" section to each chapter for which there are PUBLISHED
    # Examples tagged. include_solutions=False renders statements only,
    # producing a problems-only handout from the same corpus.
    include_examples = models.BooleanField(default=True)
    include_solutions = models.BooleanField(default=True)

    # Per-book picker: stores only the deselections relative to "everything
    # currently tagged & published". Empty list = include all (default).
    # Stale ids (deleted / unpublished / re-tagged examples) are tolerated
    # by the build pipeline at read time — no proactive pruning.
    excluded_example_ids = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class BookPart(models.Model):
    """A named part (section) within a book, containing an ordered list of chapters."""

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="parts")
    title = models.CharField(max_length=300)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["book", "order"], name="unique_part_order"),
        ]

    def __str__(self):
        return f"{self.book.title} / {self.title}"


class BookChapter(models.Model):
    """An ordered reference to a catalog chapter within a book part."""

    part = models.ForeignKey(BookPart, on_delete=models.CASCADE, related_name="book_chapters")
    chapter = models.ForeignKey(
        "catalog.Chapter",
        on_delete=models.PROTECT,  # prevent deleting a chapter that is in use
    )
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["part", "order"], name="unique_chapter_order"),
        ]

    def __str__(self):
        return f"{self.part} / {self.chapter.title}"


class BuildJob(models.Model):
    """
    Tracks a single Celery build_book task execution.

    Created when a build is enqueued; updated as the task progresses.
    One-to-one with Book — only the most recent build is tracked here.
    """

    book = models.OneToOneField(Book, on_delete=models.CASCADE, related_name="build_job")
    celery_task_id = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    # S3 key or local filesystem path to the generated PDF
    pdf_path = models.CharField(max_length=500, blank=True)

    # Filesystem path to the generated EPUB (tex4ebook output).
    epub_path = models.CharField(max_length=500, blank=True)

    # Full arara stdout/stderr captured on completion (success or failure)
    log_output = models.TextField(blank=True)

    # Human-readable error summary on failure; empty on success
    error_message = models.TextField(blank=True)

    # True when the most recent build was a "structure preview" — TOC +
    # chapter titles only, no body content. Reset to False on every
    # full build so the badge stays accurate.
    preview_structure = models.BooleanField(default=False)

    # Resolved commit SHA per chapter repo at clone time. Shape:
    #   {"OpenChapters/OpenChapters": "abc123...", ...}
    # Captured so FrozenBook can snapshot exact source state without
    # re-cloning. Empty {} for legacy jobs that pre-date this field.
    chapter_shas = models.JSONField(default=dict, blank=True)

    # Chapters dropped from the build because their LaTeX source was no
    # longer present in the cloned repo (e.g. removed from the repo after
    # the user added them to their book). The build still completes with
    # the remaining chapters; this records what was skipped so the user
    # can be told. Each entry: {"title", "repo", "subdir", "reason"}.
    # Empty [] on a clean build.
    omitted_chapters = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"BuildJob({self.book.title})"


class BuildStep(models.Model):
    """
    A single stage within a BuildJob (clone, assemble, typeset, …).

    Stages are written as the build task progresses so the user can see
    real-time progress instead of an opaque "Building…" badge for the
    full 1–10 minute window. On failure, ``log_tail`` captures the last
    few KB of build output for the stage so the build status page can
    point straight at the relevant noise.

    Reset wholesale at the start of each build, so a Book only ever has
    the steps from its most recent build.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    build_job = models.ForeignKey(
        BuildJob,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    # Internal key — stable identifier the frontend can match against
    # (e.g. for an icon map). Not shown to users directly.
    name = models.CharField(max_length=50)
    # Human-readable label shown in the progress strip.
    label = models.CharField(max_length=200)
    order = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    # Short sub-message updated during the run (e.g. "3 of 12 repos").
    detail = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    # Tail of build output captured for failed steps, bounded to ~4KB.
    log_tail = models.TextField(blank=True)

    class Meta:
        ordering = ["build_job_id", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["build_job", "order"],
                name="unique_step_order_per_job",
            ),
        ]

    def __str__(self):
        return f"BuildStep({self.build_job_id}/{self.order}:{self.name})"


def _generate_share_token() -> str:
    import secrets
    return secrets.token_urlsafe(16)


class FrozenBook(models.Model):
    """
    A pinned snapshot of a Book at a moment in time — the "Freeze for
    semester" feature. Frozen builds are immutable and accessible via a
    stable share URL that does not require login, so an instructor can
    distribute the link to students or LMS resources.

    The parent Book remains editable and re-buildable; frozen versions
    are insulated from those changes. The build artifacts are *copied*
    into a per-token directory under settings.FROZEN_OUTPUT_DIR so the
    frozen version survives even if the parent Book is later deleted
    (book FK is SET_NULL).
    """

    book = models.ForeignKey(
        Book,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="frozen_versions",
    )
    label = models.CharField(
        max_length=200,
        blank=True,
        help_text="Human label (e.g. 'Fall 2026'). Shown next to the title.",
    )
    share_token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=_generate_share_token,
    )

    # Snapshots so display + citation survive parent-Book deletion.
    title_snapshot = models.CharField(max_length=300)
    author_snapshot = models.CharField(max_length=200, blank=True)

    # Per-chapter snapshot. Shape (list of dicts, ordered as in the book):
    #   [{"chabbr", "title", "repo", "commit_sha", "last_updated"}]
    chapter_snapshot = models.JSONField(default=list, blank=True)

    # Copied build artifacts. Empty when that format wasn't part of the
    # source build (e.g. user only built PDF).
    pdf_path = models.CharField(max_length=500, blank=True)
    html_path = models.CharField(max_length=500, blank=True)
    epub_path = models.CharField(max_length=500, blank=True)

    frozen_at = models.DateTimeField(auto_now_add=True)
    frozen_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="frozen_books",
    )

    class Meta:
        ordering = ["-frozen_at"]

    def __str__(self):
        return f"FrozenBook({self.title_snapshot} @ {self.frozen_at:%Y-%m-%d})"

    @property
    def has_pdf(self) -> bool:
        return bool(self.pdf_path)

    @property
    def has_html(self) -> bool:
        return bool(self.html_path)

    @property
    def has_epub(self) -> bool:
        return bool(self.epub_path)
