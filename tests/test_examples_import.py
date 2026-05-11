"""Batch import tests — parser dry-run, commit, idempotency, gating."""

import io
import json
import zipfile

import pytest

from admin_api.models import SiteSetting
from catalog.models import Example
from catalog.services.example_import import (
    commit_report,
    parse_zip,
    report_to_dict,
)
from tests.factories import ChapterFactory


# ── Helpers ────────────────────────────────────────────────────────────


def _make_zip(manifest, files=None, *, raw_manifest=None):
    """Build an in-memory zip with the given manifest and per-entry files.

    `files` is a dict of zip-path -> bytes for everything besides the
    statement/solution defaults. `raw_manifest`, when set, overrides the
    serialized manifest bytes (used to test malformed JSON).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if raw_manifest is not None:
            zf.writestr("manifest.json", raw_manifest)
        else:
            zf.writestr("manifest.json", json.dumps(manifest))
        # default per-entry files
        for entry in manifest or []:
            d = entry.get("dir")
            if not d:
                continue
            zf.writestr(f"{d}/statement.tex", f"% statement for {d}\n2+2=4.")
            zf.writestr(f"{d}/solution.tex", f"% solution for {d}\nBy direct calc.")
        # caller-provided files override / add
        for path, data in (files or {}).items():
            zf.writestr(path, data)
    return buf.getvalue()


# ── Parser ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestParser:
    def _chapters(self):
        return {
            "AAA": ChapterFactory(chabbr="AAA"),
            "BBB": ChapterFactory(chabbr="BBB"),
        }

    def test_happy_path_two_entries(self, user):
        chs = self._chapters()
        manifest = [
            {"dir": "e1", "primary_chapter": "AAA", "chapters": ["AAA"], "difficulty": "standard"},
            {"dir": "e2", "primary_chapter": "BBB", "chapters": ["BBB"], "difficulty": "advanced"},
        ]
        report = parse_zip(zip_bytes=_make_zip(manifest), default_author=user)
        assert not report.has_errors
        assert len(report.entries) == 2
        assert report.entries[0].statement_tex.startswith("% statement for e1")
        assert report.entries[1].difficulty == "advanced"

    def test_malformed_json(self, user):
        zb = _make_zip([], raw_manifest=b"not json at all")
        report = parse_zip(zip_bytes=zb, default_author=user)
        assert report.has_errors
        assert any("not valid JSON" in g for g in report.global_errors)

    def test_missing_manifest(self, user):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("e1/statement.tex", "x")
            zf.writestr("e1/solution.tex", "y")
        report = parse_zip(zip_bytes=buf.getvalue(), default_author=user)
        assert any("manifest.json is missing" in g for g in report.global_errors)

    def test_manifest_must_be_list(self, user):
        zb = _make_zip([], raw_manifest=b'{"not": "a list"}')
        report = parse_zip(zip_bytes=zb, default_author=user)
        assert any("must be a JSON list" in g for g in report.global_errors)

    def test_unknown_chabbr(self, user):
        self._chapters()
        manifest = [
            {"dir": "e1", "primary_chapter": "ZZZ", "chapters": ["ZZZ"]},
        ]
        report = parse_zip(zip_bytes=_make_zip(manifest), default_author=user)
        # Unknown chabbr surfaces as a per-entry error, not a global one.
        assert report.has_errors
        assert any("not found" in e for e in report.entries[0].errors)

    def test_primary_not_in_chapters(self, user):
        self._chapters()
        manifest = [
            {"dir": "e1", "primary_chapter": "AAA", "chapters": ["BBB"]},
        ]
        report = parse_zip(zip_bytes=_make_zip(manifest), default_author=user)
        assert report.has_errors
        assert any("must be one of" in e for e in report.entries[0].errors)

    def test_missing_statement(self, user):
        self._chapters()
        manifest = [{"dir": "e1", "primary_chapter": "AAA", "chapters": ["AAA"]}]
        # Remove the statement file: build zip manually
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("e1/solution.tex", "solution only")
        report = parse_zip(zip_bytes=buf.getvalue(), default_author=user)
        assert any("Missing e1/statement.tex" in e for e in report.entries[0].errors)

    def test_duplicate_slug_in_manifest(self, user):
        self._chapters()
        manifest = [
            {"dir": "e1", "slug": "dup", "primary_chapter": "AAA", "chapters": ["AAA"]},
            {"dir": "e2", "slug": "dup", "primary_chapter": "AAA", "chapters": ["AAA"]},
        ]
        report = parse_zip(zip_bytes=_make_zip(manifest), default_author=user)
        assert any("Duplicate slug" in e for e in report.entries[1].errors)

    def test_invalid_difficulty(self, user):
        self._chapters()
        manifest = [{
            "dir": "e1",
            "primary_chapter": "AAA",
            "chapters": ["AAA"],
            "difficulty": "impossible",
        }]
        report = parse_zip(zip_bytes=_make_zip(manifest), default_author=user)
        assert any("difficulty" in e for e in report.entries[0].errors)

    def test_difficulty_defaults_to_standard(self, user):
        self._chapters()
        manifest = [{
            "dir": "e1",
            "primary_chapter": "AAA",
            "chapters": ["AAA"],
        }]  # no difficulty
        report = parse_zip(zip_bytes=_make_zip(manifest), default_author=user)
        assert not report.has_errors
        assert report.entries[0].difficulty == "standard"

    def test_zip_slip_blocked(self, user):
        self._chapters()
        manifest = [{
            "dir": "e1",
            "primary_chapter": "AAA",
            "chapters": ["AAA"],
        }]
        # Inject a traversal entry alongside the normal content.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("e1/statement.tex", "x")
            zf.writestr("e1/solution.tex", "y")
            zf.writestr("../etc/passwd", "evil")
        report = parse_zip(zip_bytes=buf.getvalue(), default_author=user)
        assert any("unsafe path" in g.lower() for g in report.global_errors)


# ── Commit ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCommit:
    def _setup(self):
        return ChapterFactory(chabbr="AAA")

    def test_commit_creates(self, user):
        self._setup()
        manifest = [{
            "dir": "e1", "primary_chapter": "AAA", "chapters": ["AAA"], "slug": "first",
        }]
        report = parse_zip(zip_bytes=_make_zip(manifest), default_author=user)
        assert not report.has_errors
        commit_report(report=report, default_author=user, default_status=Example.Status.PENDING)
        ex = Example.objects.get(author=user, slug="first")
        assert ex.status == Example.Status.PENDING
        assert ex.statement_tex.startswith("% statement for e1")

    def test_commit_idempotent_via_slug(self, user):
        self._setup()
        manifest = [{
            "dir": "e1", "primary_chapter": "AAA", "chapters": ["AAA"],
            "slug": "stable",
        }]
        r1 = parse_zip(zip_bytes=_make_zip(manifest), default_author=user)
        commit_report(report=r1, default_author=user, default_status=Example.Status.PENDING)
        assert Example.objects.filter(author=user, slug="stable").count() == 1

        # Re-import with updated content; the SAME row should be updated.
        manifest[0]["difficulty"] = "advanced"
        r2 = parse_zip(zip_bytes=_make_zip(manifest), default_author=user)
        assert r2.entries[0].action == "update"
        commit_report(report=r2, default_author=user, default_status=Example.Status.PENDING)
        ex = Example.objects.get(author=user, slug="stable")
        assert ex.difficulty == "advanced"
        assert Example.objects.filter(author=user, slug="stable").count() == 1

    def test_commit_atomic_on_invalid_status(self, user):
        """commit_report should refuse to write anything if default_status is bogus."""
        self._setup()
        manifest = [
            {"dir": "e1", "primary_chapter": "AAA", "chapters": ["AAA"]},
            {"dir": "e2", "primary_chapter": "AAA", "chapters": ["AAA"]},
        ]
        report = parse_zip(zip_bytes=_make_zip(manifest), default_author=user)
        assert not report.has_errors
        before = Example.objects.count()
        report = commit_report(report=report, default_author=user, default_status="bogus")
        assert report.has_errors
        assert Example.objects.count() == before


# ── HTTP gating ────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAuthorImportGating:
    """The author-side endpoints are gated by SiteSetting.author_batch_import_enabled."""

    def _zip(self):
        ChapterFactory(chabbr="AAA")
        manifest = [{"dir": "e1", "primary_chapter": "AAA", "chapters": ["AAA"]}]
        return _make_zip(manifest)

    def test_author_dry_run_blocked_when_disabled(self, auth_client):
        SiteSetting.objects.update_or_create(
            key="author_batch_import_enabled", defaults={"value": False}
        )
        resp = auth_client.post(
            "/api/examples/import/dry-run/",
            {"file": ("b.zip", io.BytesIO(self._zip()), "application/zip")},
            format="multipart",
        )
        assert resp.status_code == 403

    def test_author_dry_run_allowed_when_enabled(self, auth_client):
        SiteSetting.objects.update_or_create(
            key="author_batch_import_enabled", defaults={"value": True}
        )
        resp = auth_client.post(
            "/api/examples/import/dry-run/",
            {"file": ("b.zip", io.BytesIO(self._zip()), "application/zip")},
            format="multipart",
        )
        assert resp.status_code == 200
        assert resp.data["summary"]["create"] == 1

    def test_author_commit_blocked_when_disabled(self, auth_client):
        SiteSetting.objects.update_or_create(
            key="author_batch_import_enabled", defaults={"value": False}
        )
        resp = auth_client.post(
            "/api/examples/import/commit/",
            {
                "file": ("b.zip", io.BytesIO(self._zip()), "application/zip"),
                "default_status": "draft",
            },
            format="multipart",
        )
        assert resp.status_code == 403

    def test_author_cannot_self_publish(self, auth_client, user):
        """ALLOWED_DEFAULT_STATUSES = {DRAFT, PENDING} for authors."""
        SiteSetting.objects.update_or_create(
            key="author_batch_import_enabled", defaults={"value": True}
        )
        resp = auth_client.post(
            "/api/examples/import/commit/",
            {
                "file": ("b.zip", io.BytesIO(self._zip()), "application/zip"),
                "default_status": "published",
            },
            format="multipart",
        )
        assert resp.status_code == 400

    def test_author_commit_to_pending(self, auth_client, user):
        SiteSetting.objects.update_or_create(
            key="author_batch_import_enabled", defaults={"value": True}
        )
        resp = auth_client.post(
            "/api/examples/import/commit/",
            {
                "file": ("b.zip", io.BytesIO(self._zip()), "application/zip"),
                "default_status": "pending",
            },
            format="multipart",
        )
        assert resp.status_code == 201
        ex = Example.objects.get(author=user)
        assert ex.status == Example.Status.PENDING


@pytest.mark.django_db
class TestAdminImport:
    def _zip(self):
        ChapterFactory(chabbr="AAA")
        manifest = [{"dir": "e1", "primary_chapter": "AAA", "chapters": ["AAA"]}]
        return _make_zip(manifest)

    def test_admin_can_self_publish(self, staff_client, staff_user):
        resp = staff_client.post(
            "/api/admin/examples/import/commit/",
            {
                "file": ("b.zip", io.BytesIO(self._zip()), "application/zip"),
                "default_status": "published",
            },
            format="multipart",
        )
        assert resp.status_code == 201
        ex = Example.objects.get(author=staff_user)
        assert ex.status == Example.Status.PUBLISHED

    def test_admin_rejects_unknown_status(self, staff_client):
        resp = staff_client.post(
            "/api/admin/examples/import/commit/",
            {
                "file": ("b.zip", io.BytesIO(self._zip()), "application/zip"),
                "default_status": "bogus",
            },
            format="multipart",
        )
        assert resp.status_code == 400

    def test_admin_rejects_dirty_report(self, staff_client):
        """If parse finds errors, commit should 400 and write nothing."""
        ChapterFactory(chabbr="AAA")
        manifest = [{
            "dir": "e1", "primary_chapter": "ZZZ", "chapters": ["ZZZ"],
        }]
        zb = _make_zip(manifest)
        before = Example.objects.count()
        resp = staff_client.post(
            "/api/admin/examples/import/commit/",
            {
                "file": ("b.zip", io.BytesIO(zb), "application/zip"),
                "default_status": "pending",
            },
            format="multipart",
        )
        assert resp.status_code == 400
        assert Example.objects.count() == before

    def test_non_admin_blocked_from_admin_endpoint(self, auth_client):
        resp = auth_client.post(
            "/api/admin/examples/import/commit/",
            {"file": ("b.zip", io.BytesIO(self._zip()), "application/zip")},
            format="multipart",
        )
        assert resp.status_code == 403


@pytest.mark.django_db
class TestReportShape:
    def test_report_to_dict_summary(self, user):
        ChapterFactory(chabbr="AAA")
        manifest = [
            {"dir": "e1", "primary_chapter": "AAA", "chapters": ["AAA"]},
            {"dir": "e2", "primary_chapter": "AAA", "chapters": ["AAA"]},
        ]
        report = parse_zip(zip_bytes=_make_zip(manifest), default_author=user)
        d = report_to_dict(report)
        assert "summary" in d
        assert d["summary"]["create"] == 2
        assert "entries" in d
