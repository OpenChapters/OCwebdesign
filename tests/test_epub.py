"""Tests for the EPUB build path and format-selector extensions.

The full tex4ebook subprocess is heavy (clones repos, runs LaTeX), so
these tests cover the wiring around it: format-selector validation,
task scheduling, model fields, download endpoints, and email body.
"""

from unittest.mock import patch
from pathlib import Path

import pytest
from django.urls import reverse

from books.models import Book, BuildJob
from tests.factories import (
    BookChapterFactory,
    BookFactory,
    BookPartFactory,
    BuildJobFactory,
    ChapterFactory,
    UserFactory,
)


# ── BuildFormat / trigger view ────────────────────────────────────────────────

def _book_with_chapter(user):
    book = BookFactory(user=user)
    part = BookPartFactory(book=book, order=0)
    BookChapterFactory(part=part, chapter=ChapterFactory(), order=0)
    return book


def test_trigger_accepts_epub_format(user, auth_client):
    book = _book_with_chapter(user)
    with patch("books.views.build_book_epub.delay") as delay:
        resp = auth_client.post(
            reverse("build-trigger", args=[book.id]),
            {"format": "epub"}, format="json",
        )
    assert resp.status_code == 202, resp.json()
    assert delay.called
    book.refresh_from_db()
    assert book.last_build_format == "epub"


def test_trigger_accepts_all_format_and_chains_three_tasks(user, auth_client):
    book = _book_with_chapter(user)
    with patch("celery.chain") as chain_mock:
        chain_mock.return_value.delay = lambda: None
        resp = auth_client.post(
            reverse("build-trigger", args=[book.id]),
            {"format": "all"}, format="json",
        )
    assert resp.status_code == 202
    # The chain should have been called with three signatures
    args = chain_mock.call_args.args
    assert len(args) == 3


def test_trigger_both_chains_pdf_then_html_only(user, auth_client):
    """In 1.2, "both" stays at PDF+HTML — EPUB is deferred. The "all"
    enum is still accepted (and chains all three) but isn't exposed
    in the UI selector.
    """
    book = _book_with_chapter(user)
    with patch("celery.chain") as chain_mock:
        chain_mock.return_value.delay = lambda: None
        resp = auth_client.post(
            reverse("build-trigger", args=[book.id]),
            {"format": "both"}, format="json",
        )
    assert resp.status_code == 202
    book.refresh_from_db()
    assert book.last_build_format == "both"
    # Exactly two task signatures in the chain — PDF + HTML.
    assert len(chain_mock.call_args.args) == 2


def test_trigger_rejects_unknown_format(user, auth_client):
    book = _book_with_chapter(user)
    resp = auth_client.post(
        reverse("build-trigger", args=[book.id]),
        {"format": "mobi"}, format="json",
    )
    assert resp.status_code == 400


# ── Book/BuildJob model + serializer ──────────────────────────────────────────

def test_book_has_epub_property_reflects_built_state(user, tmp_path):
    book = BookFactory(user=user, status=Book.Status.COMPLETE)
    job = BuildJobFactory(book=book)
    assert book.epub_path == "" and not book.epub_built_at

    epub = tmp_path / "x.epub"
    epub.write_bytes(b"PK")
    from django.utils import timezone
    book.epub_path = str(epub)
    book.epub_built_at = timezone.now()
    job.epub_path = str(epub)
    book.save()
    job.save()

    from books.serializers import BookSerializer
    data = BookSerializer(book).data
    assert data["has_epub"] is True


def test_chapter_shas_persisted_on_buildjob(user):
    book = BookFactory(user=user)
    job = BuildJobFactory(book=book, chapter_shas={"a/b": "deadbeef"})
    job.refresh_from_db()
    assert job.chapter_shas == {"a/b": "deadbeef"}


# ── Download endpoints ───────────────────────────────────────────────────────

def test_download_epub_owner_only(user, auth_client, tmp_path):
    book = BookFactory(user=user, status=Book.Status.COMPLETE)
    epub = tmp_path / "ok.epub"
    epub.write_bytes(b"PK\x03\x04fake")
    from django.utils import timezone
    book.epub_path = str(epub)
    book.epub_built_at = timezone.now()
    book.save()

    resp = auth_client.get(reverse("download-epub", args=[book.id]))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/epub+zip"


def test_download_epub_404_when_not_built(user, auth_client):
    book = BookFactory(user=user, status=Book.Status.COMPLETE)
    resp = auth_client.get(reverse("download-epub", args=[book.id]))
    assert resp.status_code == 404


def test_download_epub_404_for_other_user(user, auth_client, tmp_path):
    other = UserFactory()
    book = BookFactory(user=other, status=Book.Status.COMPLETE)
    epub = tmp_path / "x.epub"; epub.write_bytes(b"PK")
    from django.utils import timezone
    book.epub_path = str(epub); book.epub_built_at = timezone.now(); book.save()
    resp = auth_client.get(reverse("download-epub", args=[book.id]))
    assert resp.status_code == 404


# ── Delivery email ────────────────────────────────────────────────────────────

def test_deliver_epub_skips_when_no_epub_built(user, settings):
    settings.EMAIL_HOST = "smtp.example.com"
    book = BookFactory(user=user, status=Book.Status.COMPLETE)
    from books.tasks import deliver_epub
    with patch("django.core.mail.EmailMultiAlternatives.send") as send:
        deliver_epub(book.id)
    assert not send.called


def test_deliver_epub_sends_email_when_epub_present(user, settings, tmp_path):
    settings.EMAIL_HOST = "smtp.example.com"
    settings.SITE_URL = "https://example.test"
    book = BookFactory(user=user, status=Book.Status.COMPLETE)
    epub = tmp_path / "x.epub"; epub.write_bytes(b"PK")
    from django.utils import timezone
    book.epub_path = str(epub); book.epub_built_at = timezone.now(); book.save()
    BuildJobFactory(book=book, epub_path=str(epub))

    from books.tasks import deliver_epub
    with patch("django.core.mail.EmailMultiAlternatives.send") as send:
        deliver_epub(book.id)
    assert send.called
