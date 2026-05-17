"""Tests for the FrozenBook (semester snapshot) feature."""

from pathlib import Path

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from books.models import Book, FrozenBook
from tests.factories import (
    BookChapterFactory,
    BookFactory,
    BookPartFactory,
    BuildJobFactory,
    ChapterFactory,
    UserFactory,
)


def _make_complete_book(user, *, with_pdf=True, with_html=False, with_epub=False,
                       chapter_shas=None, tmp_path=None):
    """Build a Book in COMPLETE state with on-disk fake artifacts."""
    book = BookFactory(user=user, status=Book.Status.COMPLETE)
    part = BookPartFactory(book=book, order=0)
    BookChapterFactory(part=part, chapter=ChapterFactory(), order=0)
    BookChapterFactory(part=part, chapter=ChapterFactory(), order=1)

    job = BuildJobFactory(book=book, chapter_shas=chapter_shas or {})
    if with_pdf:
        pdf = tmp_path / f"book_{book.id}.pdf"
        pdf.write_bytes(b"%PDF-1.4\nfake\n%%EOF\n")
        job.pdf_path = str(pdf)
    if with_epub:
        epub = tmp_path / f"book_{book.id}.epub"
        epub.write_bytes(b"PK\x03\x04fake epub")
        job.epub_path = str(epub)
    job.save()
    if with_html:
        html_dir = tmp_path / f"book_{book.id}_html"
        html_dir.mkdir()
        (html_dir / "index.html").write_text("<html><body>hi</body></html>")
        book.html_path = str(html_dir)
        from django.utils import timezone
        book.html_built_at = timezone.now()
        book.save()
    return book, job


@pytest.fixture
def frozen_root(tmp_path, settings):
    """Re-point FROZEN_OUTPUT_DIR at a per-test tmp directory."""
    root = tmp_path / "frozen"
    root.mkdir()
    settings.FROZEN_OUTPUT_DIR = str(root)
    return root


# ── Model basics ──────────────────────────────────────────────────────────────

def test_share_token_default_is_unique_and_url_safe(db):
    from books.models import _generate_share_token
    tokens = {_generate_share_token() for _ in range(50)}
    assert len(tokens) == 50
    for t in tokens:
        assert all(c.isalnum() or c in "-_" for c in t)
        assert 16 <= len(t) <= 64


def test_has_format_props_reflect_path_presence(db):
    f = FrozenBook(
        title_snapshot="x",
        pdf_path="/tmp/x.pdf",
        html_path="",
        epub_path="/tmp/x.epub",
    )
    assert f.has_pdf is True
    assert f.has_html is False
    assert f.has_epub is True


# ── Freeze endpoint ───────────────────────────────────────────────────────────

def test_freeze_succeeds_for_complete_pdf_only_book(user, auth_client, tmp_path, frozen_root):
    book, _ = _make_complete_book(user, with_pdf=True, tmp_path=tmp_path,
                                  chapter_shas={"OpenChapters/Foo": "abc123"})
    url = reverse("book-freeze", args=[book.id])

    resp = auth_client.post(url, {"label": "Fall 2026"}, format="json")
    assert resp.status_code == 201, resp.json()

    data = resp.json()
    assert data["label"] == "Fall 2026"
    assert data["has_pdf"] is True
    assert data["has_html"] is False
    assert data["has_epub"] is False
    assert data["title_snapshot"] == book.title
    assert len(data["chapter_snapshot"]) == 2
    assert data["share_token"]

    # On-disk copy exists, distinct from the source.
    frozen = FrozenBook.objects.get(pk=data["id"])
    assert Path(frozen.pdf_path).is_file()
    assert frozen.pdf_path.startswith(str(frozen_root))


def test_freeze_404_when_book_not_owned(user, auth_client, tmp_path, frozen_root):
    other = UserFactory()
    book, _ = _make_complete_book(other, tmp_path=tmp_path)
    resp = auth_client.post(reverse("book-freeze", args=[book.id]), {}, format="json")
    assert resp.status_code == 404


def test_freeze_409_when_book_not_complete(user, auth_client, tmp_path, frozen_root):
    book = BookFactory(user=user, status=Book.Status.DRAFT)
    resp = auth_client.post(reverse("book-freeze", args=[book.id]), {}, format="json")
    assert resp.status_code == 409


def test_freeze_409_when_no_artifacts_on_disk(user, auth_client, frozen_root):
    book = BookFactory(user=user, status=Book.Status.COMPLETE)
    BuildJobFactory(book=book, pdf_path="/nonexistent/path.pdf")
    resp = auth_client.post(reverse("book-freeze", args=[book.id]), {}, format="json")
    assert resp.status_code == 409


def test_freeze_copies_html_directory_and_epub(user, auth_client, tmp_path, frozen_root):
    book, _ = _make_complete_book(
        user, with_pdf=True, with_html=True, with_epub=True, tmp_path=tmp_path,
    )
    resp = auth_client.post(reverse("book-freeze", args=[book.id]),
                            {"label": "Spring 2027"}, format="json")
    assert resp.status_code == 201
    frozen = FrozenBook.objects.get(pk=resp.json()["id"])
    assert Path(frozen.pdf_path).is_file()
    assert Path(frozen.html_path).is_dir()
    assert (Path(frozen.html_path) / "index.html").read_text() == "<html><body>hi</body></html>"
    assert Path(frozen.epub_path).is_file()


def test_freeze_chapter_snapshot_includes_commit_sha(user, auth_client, tmp_path, frozen_root):
    # The factory creates chapters with sequential github_repo values like
    # "test/repo-N". The chapter_shas dict maps repo names to SHAs.
    shas = {}
    book, _ = _make_complete_book(user, tmp_path=tmp_path, chapter_shas=shas)
    # Backfill SHAs for the actual repos that ended up on the chapters.
    chapter_repos = list(
        book.parts.values_list("book_chapters__chapter__github_repo", flat=True)
    )
    shas = {r: f"sha-{i:04x}" * 10 for i, r in enumerate(chapter_repos)}
    book.build_job.chapter_shas = shas
    book.build_job.save()

    resp = auth_client.post(reverse("book-freeze", args=[book.id]), {}, format="json")
    assert resp.status_code == 201
    snap = resp.json()["chapter_snapshot"]
    for entry in snap:
        assert entry["commit_sha"] == shas[entry["repo"]]


# ── Owner list + delete ───────────────────────────────────────────────────────

def test_owner_list_returns_only_own_book_frozens(user, auth_client, tmp_path, frozen_root):
    book, _ = _make_complete_book(user, tmp_path=tmp_path)
    other_book, _ = _make_complete_book(user, tmp_path=tmp_path)
    auth_client.post(reverse("book-freeze", args=[book.id]), {"label": "A"}, format="json")
    auth_client.post(reverse("book-freeze", args=[book.id]), {"label": "B"}, format="json")
    auth_client.post(reverse("book-freeze", args=[other_book.id]), {"label": "C"}, format="json")

    resp = auth_client.get(reverse("book-frozen-list", args=[book.id]))
    assert resp.status_code == 200
    labels = sorted(f["label"] for f in resp.json())
    assert labels == ["A", "B"]


def test_owner_delete_removes_record_and_files(user, auth_client, tmp_path, frozen_root):
    book, _ = _make_complete_book(user, tmp_path=tmp_path)
    created = auth_client.post(
        reverse("book-freeze", args=[book.id]), {}, format="json",
    ).json()
    frozen_dir = frozen_root / created["share_token"]
    assert frozen_dir.is_dir()

    resp = auth_client.delete(reverse("frozen-manage", args=[created["id"]]))
    assert resp.status_code == 204
    assert not FrozenBook.objects.filter(pk=created["id"]).exists()
    assert not frozen_dir.exists()


def test_owner_delete_404_for_other_users_frozen(user, auth_client, tmp_path, frozen_root):
    other = UserFactory()
    other_client = APIClient()
    from rest_framework_simplejwt.tokens import RefreshToken
    other_client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(other).access_token}")
    book, _ = _make_complete_book(other, tmp_path=tmp_path)
    created = other_client.post(
        reverse("book-freeze", args=[book.id]), {}, format="json",
    ).json()
    resp = auth_client.delete(reverse("frozen-manage", args=[created["id"]]))
    assert resp.status_code == 404
    assert FrozenBook.objects.filter(pk=created["id"]).exists()


# ── Public read by token ──────────────────────────────────────────────────────

def test_public_metadata_works_without_auth(user, auth_client, api_client, tmp_path, frozen_root):
    book, _ = _make_complete_book(user, with_pdf=True, tmp_path=tmp_path)
    created = auth_client.post(
        reverse("book-freeze", args=[book.id]),
        {"label": "Fall 2026"}, format="json",
    ).json()

    resp = api_client.get(reverse("frozen-public", args=[created["share_token"]]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "Fall 2026"
    assert body["title_snapshot"] == book.title
    assert body["has_pdf"] is True
    # share_token must NOT be exposed in public payload — it's already the URL
    assert "share_token" not in body


def test_public_pdf_download_works_without_auth(user, auth_client, api_client, tmp_path, frozen_root):
    book, _ = _make_complete_book(user, with_pdf=True, tmp_path=tmp_path)
    created = auth_client.post(
        reverse("book-freeze", args=[book.id]), {}, format="json",
    ).json()
    resp = api_client.get(reverse("frozen-pdf", args=[created["share_token"]]))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"


def test_public_view_404s_for_bad_token(db, api_client):
    resp = api_client.get(reverse("frozen-public", args=["nope-not-a-token"]))
    assert resp.status_code == 404


# ── Insulation from parent-book deletion ──────────────────────────────────────

def test_frozen_artifacts_survive_parent_book_deletion(user, auth_client, tmp_path,
                                                       frozen_root, api_client):
    book, _ = _make_complete_book(user, with_pdf=True, tmp_path=tmp_path)
    created = auth_client.post(
        reverse("book-freeze", args=[book.id]), {}, format="json",
    ).json()

    book.delete()

    # FrozenBook row keeps its snapshot data (book FK is SET_NULL).
    frozen = FrozenBook.objects.get(pk=created["id"])
    assert frozen.book is None
    assert frozen.title_snapshot  # snapshot still readable
    assert Path(frozen.pdf_path).is_file()

    # Public PDF download still works.
    resp = api_client.get(reverse("frozen-pdf", args=[created["share_token"]]))
    assert resp.status_code == 200
