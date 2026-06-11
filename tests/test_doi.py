"""Tests for chapter DOI minting.

Exercises the orchestrator (catalog.services.doi.ensure_chapter_dois) and the
placeholder DataCite client (catalog.services.datacite), plus the DOI fields
exposed by the chapter serializers.

All tests run with DATACITE_ENABLED=False (the default in test settings), so
the DataCite client returns deterministic placeholder DOIs and makes no network
call. The minting *contract* — concept-once + version-on-bump, idempotent,
atomic, warn-and-continue — is what's under test, independent of the eventual
real DataCite integration.
"""

import pytest
from django.db import IntegrityError

from catalog.models import ChapterDOIVersion
from catalog.services import datacite
from catalog.services.doi import ensure_chapter_dois
from tests.factories import ChapterFactory


# ── Placeholder DataCite client ───────────────────────────────────────────────

@pytest.mark.django_db
class TestPlaceholderClient:
    def test_placeholder_dois_are_deterministic(self):
        ch = ChapterFactory(chabbr="FOURIE")
        assert datacite.mint_concept_doi(ch) == datacite.mint_concept_doi(ch)
        assert datacite.mint_version_doi(ch, "1.0") == datacite.mint_version_doi(ch, "1.0")

    def test_placeholder_concept_and_version_differ(self):
        ch = ChapterFactory(chabbr="FOURIE")
        concept = datacite.mint_concept_doi(ch)
        v10 = datacite.mint_version_doi(ch, "1.0")
        v11 = datacite.mint_version_doi(ch, "1.1")
        assert concept != v10 != v11
        # Uses the configured (test) prefix so it's recognizable as not-real.
        assert all(d.startswith("10.5072/") for d in (concept, v10, v11))


# ── ensure_chapter_dois orchestration ─────────────────────────────────────────

@pytest.mark.django_db
class TestEnsureChapterDois:
    def test_unversioned_chapter_mints_nothing(self):
        ch = ChapterFactory(version="")
        ensure_chapter_dois(ch, commit_sha="abc123")
        ch.refresh_from_db()
        assert ch.concept_doi == ""
        assert ch.doi_versions.count() == 0

    def test_first_versioned_sync_mints_concept_and_version(self):
        ch = ChapterFactory(chabbr="FIRST", version="1.0")
        ensure_chapter_dois(ch, commit_sha="aaa111")
        ch.refresh_from_db()

        assert ch.concept_doi != ""
        rows = list(ch.doi_versions.all())
        assert len(rows) == 1
        row = rows[0]
        assert row.version == "1.0"
        assert row.doi != ""
        assert row.commit_sha == "aaa111"
        assert row.is_current is True

    def test_resync_same_version_is_idempotent(self):
        ch = ChapterFactory(chabbr="IDEM", version="1.0")
        ensure_chapter_dois(ch, commit_sha="aaa111")
        first_concept = ch.concept_doi
        first_doi = ch.doi_versions.get().doi

        # Re-sync with the same version: no new row, no re-mint.
        ensure_chapter_dois(ch, commit_sha="aaa111")
        ch.refresh_from_db()

        assert ch.concept_doi == first_concept
        assert ch.doi_versions.count() == 1
        assert ch.doi_versions.get().doi == first_doi

    def test_version_bump_adds_row_and_moves_current(self):
        ch = ChapterFactory(chabbr="BUMP", version="1.0")
        ensure_chapter_dois(ch, commit_sha="aaa111")

        ch.version = "1.1"
        ch.save(update_fields=["version"])
        ensure_chapter_dois(ch, commit_sha="bbb222")
        ch.refresh_from_db()

        rows = {r.version: r for r in ch.doi_versions.all()}
        assert set(rows) == {"1.0", "1.1"}          # both retained
        assert rows["1.0"].is_current is False       # old demoted
        assert rows["1.1"].is_current is True        # new is current
        assert rows["1.1"].commit_sha == "bbb222"
        # Exactly one current version at any time.
        assert ch.doi_versions.filter(is_current=True).count() == 1

    def test_concept_doi_minted_once_across_versions(self):
        ch = ChapterFactory(chabbr="ONCE", version="1.0")
        ensure_chapter_dois(ch, commit_sha="aaa111")
        concept = ch.concept_doi

        ch.version = "2.0"
        ch.save(update_fields=["version"])
        ensure_chapter_dois(ch, commit_sha="ccc333")
        ch.refresh_from_db()

        assert ch.concept_doi == concept  # unchanged

    def test_minting_failure_does_not_create_row_or_raise(self, monkeypatch):
        """A DataCite failure is logged and swallowed (warn-and-continue), and
        leaves no partial version row (atomic)."""
        def boom(*args, **kwargs):
            raise datacite.DataCiteError("simulated DataCite outage")

        monkeypatch.setattr(datacite, "mint_version_doi", boom)
        ch = ChapterFactory(chabbr="FAIL", version="1.0")

        # Must not raise.
        ensure_chapter_dois(ch, commit_sha="aaa111")
        ch.refresh_from_db()

        # Concept DOI was committed independently before the version mint;
        # the failed version mint creates no row.
        assert ch.concept_doi != ""
        assert ch.doi_versions.count() == 0

    def test_retry_after_failure_succeeds(self, monkeypatch):
        """After a transient failure, the next sync mints cleanly."""
        def boom(*args, **kwargs):
            raise datacite.DataCiteError("transient")

        monkeypatch.setattr(datacite, "mint_version_doi", boom)
        ch = ChapterFactory(chabbr="RETRY", version="1.0")
        ensure_chapter_dois(ch, commit_sha="aaa111")
        assert ch.doi_versions.count() == 0

        # DataCite recovers; un-patch and re-sync.
        monkeypatch.undo()
        ensure_chapter_dois(ch, commit_sha="aaa111")
        ch.refresh_from_db()
        assert ch.doi_versions.count() == 1
        assert ch.doi_versions.get().is_current is True


# ── Model constraints ─────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestChapterDOIVersionModel:
    def test_unique_version_per_chapter(self):
        ch = ChapterFactory(chabbr="UNIQ")
        ChapterDOIVersion.objects.create(chapter=ch, version="1.0", doi="x")
        with pytest.raises(IntegrityError):
            ChapterDOIVersion.objects.create(chapter=ch, version="1.0", doi="y")


# ── Serializer exposure ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSerializerDOIFields:
    def test_chapter_serializer_exposes_doi_fields(self):
        from catalog.serializers import ChapterSerializer

        ch = ChapterFactory(chabbr="SER", version="1.0")
        ensure_chapter_dois(ch, commit_sha="dead42")
        ch.refresh_from_db()

        data = ChapterSerializer(ch).data
        assert data["version"] == "1.0"
        assert data["concept_doi"] == ch.concept_doi
        assert data["current_version_doi"] == ch.doi_versions.get().doi
        assert len(data["doi_versions"]) == 1
        assert data["doi_versions"][0]["commit_sha"] == "dead42"
        assert data["doi_versions"][0]["is_current"] is True

    def test_admin_serializer_exposes_doi_fields_readonly(self):
        from admin_api.serializers import AdminChapterSerializer

        ch = ChapterFactory(chabbr="ADM", version="1.0")
        ensure_chapter_dois(ch, commit_sha="beef99")
        ch.refresh_from_db()

        ser = AdminChapterSerializer(ch)
        data = ser.data
        assert data["version"] == "1.0"
        assert data["concept_doi"] == ch.concept_doi
        assert data["current_version_doi"] == ch.doi_versions.get().doi
        # DOI/version fields are read-only in admin (sourced from sync, not editable).
        for field in ("version", "concept_doi", "current_version_doi"):
            assert ser.fields[field].read_only is True
