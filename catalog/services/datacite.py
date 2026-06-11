"""DataCite DOI client.

PLACEHOLDER — this module does NOT call DataCite yet.

It is the single seam through which the platform mints DOIs. While
``settings.DATACITE_ENABLED`` is False (the default), ``mint_concept_doi`` and
``mint_version_doi`` return deterministic placeholder DOIs under DataCite's
shared TEST prefix (10.5072) and make no network call, so the full pipeline —
trigger detection, version history, serialization, display — can be built and
tested now.

When the real integration is wired up later:

* Set ``DATACITE_ENABLED=True`` and supply ``DATACITE_REPO_ID`` /
  ``DATACITE_PASSWORD`` (and a real ``DATACITE_PREFIX``).
* Replace the bodies guarded by ``DATACITE_ENABLED`` with real DataCite REST
  calls (``httpx`` + HTTP Basic auth, following the retry conventions in
  ``catalog/git_provider.py``): POST a draft DOI, attach metadata, and publish.
* For version DOIs, also register the DataCite relation metadata linking the
  version DOI to the concept DOI (``IsVersionOf`` / ``IsNewVersionOf`` /
  ``IsPreviousVersionOf``) and point the concept DOI at the newest version.

The return contract — a DOI string — is identical in both modes, so callers in
``catalog/services/doi.py`` never change.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class DataCiteError(Exception):
    """Raised when a real DataCite API call fails. Callers treat this as a
    transient minting failure (logged, retried on next sync) rather than a
    hard error that aborts a chapter sync."""


def _slug(value: str) -> str:
    """Normalize a string into a DOI-suffix-safe token."""
    return "".join(c if c.isalnum() else "-" for c in value.lower()).strip("-")


def _placeholder_doi(chabbr: str, suffix: str) -> str:
    """Build a deterministic, obviously-fake DOI.

    Uses the configured (test) prefix so it is clearly recognizable as
    not-yet-real, e.g. ``10.5072/openchapters.fourie.concept`` or
    ``10.5072/openchapters.fourie.1-0``.
    """
    prefix = settings.DATACITE_PREFIX
    return f"{prefix}/openchapters.{_slug(chabbr)}.{_slug(suffix)}"


def mint_concept_doi(chapter) -> str:
    """Mint (or return) the persistent concept DOI for a chapter.

    Returns the DOI string. Raises ``DataCiteError`` on a real API failure.
    """
    if not settings.DATACITE_ENABLED:
        doi = _placeholder_doi(chapter.chabbr, "concept")
        logger.info(
            "DataCite disabled: returning placeholder concept DOI %s for chapter %s",
            doi, chapter.chabbr,
        )
        return doi

    # TODO: real DataCite concept-DOI minting (POST draft + publish).
    raise NotImplementedError("Real DataCite concept-DOI minting is not yet wired up")


def mint_version_doi(chapter, version: str, commit_sha: str = "") -> str:
    """Mint a version DOI for ``version`` under the chapter's concept DOI.

    ``commit_sha`` is the source commit the version pins (recorded for metadata
    and provenance). Returns the DOI string; raises ``DataCiteError`` on a real
    API failure.
    """
    if not settings.DATACITE_ENABLED:
        doi = _placeholder_doi(chapter.chabbr, version or "unversioned")
        logger.info(
            "DataCite disabled: returning placeholder version DOI %s for chapter %s v%s",
            doi, chapter.chabbr, version,
        )
        return doi

    # TODO: real DataCite version-DOI minting; also register IsVersionOf /
    # IsNewVersionOf relations and repoint the concept DOI at this version.
    raise NotImplementedError("Real DataCite version-DOI minting is not yet wired up")
