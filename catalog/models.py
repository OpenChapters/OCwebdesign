from django.db import models


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
    authors = models.JSONField(default=list)
    description = models.TextField(blank=True)

    # List of section headings from chapter.json, shown in TOC hover preview
    toc = models.JSONField(default=list)

    # Raw GitHub URL for cover image, served directly to the browser
    cover_image_url = models.URLField(blank=True)

    # Full path to the LaTeX entry file from the repo root,
    # e.g. "src/LinearAlgebra/LinearAlgebra.tex"
    latex_entry_file = models.CharField(max_length=200)

    keywords = models.JSONField(default=list)

    chapter_type = models.CharField(
        max_length=20,
        choices=ChapterType.choices,
        default=ChapterType.TOPICAL,
    )

    # Unique chapter abbreviation used in \label and \ref, e.g. "LINALG"
    chabbr = models.CharField(max_length=20, blank=True)

    # List of chabbr values for foundational chapters this chapter cross-references.
    # Used by the frontend to auto-include required foundational chapters.
    depends_on = models.JSONField(default=list)

    # False for template/placeholder chapters not ready for inclusion in builds.
    published = models.BooleanField(default=True)

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
