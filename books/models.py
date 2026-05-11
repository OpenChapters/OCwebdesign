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

    last_build_format = models.CharField(
        max_length=8,
        choices=BuildFormat.choices,
        default=BuildFormat.PDF,
        help_text="Format selected for the most recent build; used by Retry.",
    )

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

    # Full arara stdout/stderr captured on completion (success or failure)
    log_output = models.TextField(blank=True)

    # Human-readable error summary on failure; empty on success
    error_message = models.TextField(blank=True)

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
