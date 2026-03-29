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
