"""Chapter DOI orchestration.

``ensure_chapter_dois`` is the single entry point the sync pipeline calls for
each chapter. It implements the concept-DOI + version-DOI model:

* A **concept DOI** is minted once per chapter (``Chapter.concept_doi``) and
  always resolves to the latest version.
* A **version DOI** (``ChapterDOIVersion``) is minted only when the chapter's
  ``version`` string changes — i.e. when no row yet exists for the current
  ``(chapter, version)`` pair. This is the explicit "new citable version"
  signal; routine edits that don't bump ``version`` mint nothing.

The function is idempotent (safe to call on every sync) and never raises on a
DataCite failure: minting problems are logged as warnings and retried on the
next sync, so DOI registration can never block a catalog update (the
warn-and-continue policy).

Actual DOI strings come from :mod:`catalog.services.datacite`, which currently
returns placeholders. This module is unaffected by that swap.
"""

import logging

from django.db import transaction

from catalog.models import ChapterDOIVersion
from catalog.services import datacite

logger = logging.getLogger(__name__)


def ensure_chapter_dois(chapter, commit_sha: str = "") -> None:
    """Mint any DOIs this chapter is due, idempotently.

    * No-op if the chapter is unversioned (empty ``version``).
    * Mints the concept DOI if the chapter has none yet.
    * Mints a version DOI (and records it as the current version) if no
      ``ChapterDOIVersion`` row exists for the chapter's current ``version``.

    ``commit_sha`` is the source commit the version DOI should pin, captured by
    the caller at sync time. Failures are logged and swallowed.
    """
    version = (chapter.version or "").strip()
    if not version:
        # Unversioned chapter: nothing to mint.
        return

    try:
        _ensure_concept_doi(chapter)
        _ensure_version_doi(chapter, version, commit_sha)
    except Exception:
        # Warn-and-continue: a DOI failure must never abort a chapter sync.
        logger.warning(
            "DOI minting failed for chapter %s (version %s); will retry next sync",
            chapter.chabbr, version, exc_info=True,
        )


def _ensure_concept_doi(chapter) -> None:
    """Mint and persist the chapter's concept DOI if it doesn't have one.

    Committed independently of version minting so that a later version-DOI
    failure doesn't discard a concept DOI that may already have been registered
    remotely.
    """
    if chapter.concept_doi:
        return
    doi = datacite.mint_concept_doi(chapter)
    chapter.concept_doi = doi
    chapter.save(update_fields=["concept_doi"])
    logger.info("Minted concept DOI %s for chapter %s", doi, chapter.chabbr)


def _ensure_version_doi(chapter, version: str, commit_sha: str) -> None:
    """Mint a version DOI for ``version`` if no row exists for it yet.

    The mint + history write are atomic: if minting fails the row is not
    created and the previous current-version pointer is untouched, so the next
    sync retries cleanly.
    """
    if chapter.doi_versions.filter(version=version).exists():
        return

    with transaction.atomic():
        doi = datacite.mint_version_doi(chapter, version, commit_sha)
        # Demote any prior current version before recording the new one.
        chapter.doi_versions.filter(is_current=True).update(is_current=False)
        ChapterDOIVersion.objects.create(
            chapter=chapter,
            version=version,
            doi=doi,
            commit_sha=commit_sha,
            is_current=True,
        )
    logger.info(
        "Minted version DOI %s for chapter %s v%s (commit %s)",
        doi, chapter.chabbr, version, commit_sha or "?",
    )
