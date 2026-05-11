"""Tests for the "structure preview" build path.

These exercise the request-data assembly and the BuildTriggerView's
preview_structure flag handling. The full Celery task isn't run here
(that needs LaTeX in the test environment), but the JSON payload it
would consume is verified end-to-end.
"""

import json
from unittest.mock import patch

import pytest

from books.models import Book
from books.tasks import _build_request_data
from tests.factories import (
    BookChapterFactory,
    BookFactory,
    BookPartFactory,
    ChapterFactory,
)


@pytest.mark.django_db
class TestBuildRequestDataPreview:
    def test_preview_flag_propagates(self):
        book = BookFactory()
        data = _build_request_data(book, preview_structure=True)
        assert data["preview_structure"] is True

    def test_preview_flag_defaults_false(self):
        book = BookFactory()
        data = _build_request_data(book)
        assert data["preview_structure"] is False

    def test_chapter_titles_attached(self):
        book = BookFactory()
        part = BookPartFactory(book=book, title="Part I", order=0)
        ch = ChapterFactory(
            title="Quaternions and Rotations",
            github_repo="OpenChapters/OpenChapters",
            chapter_subdir="src/Quaternions",
            latex_entry_file="src/Quaternions/Quaternions.tex",
        )
        BookChapterFactory(part=part, chapter=ch, order=0)

        data = _build_request_data(book, preview_structure=True)
        assert data["parts"][0]["chapters"][0]["title"] == "Quaternions and Rotations"


@pytest.mark.django_db
class TestBuildTriggerPreview:
    """POST /api/books/<pk>/build/ with preview_structure=true."""

    def _book_for(self, user):
        book = BookFactory(user=user)
        # Mark complete so the trigger view allows a fresh build.
        book.status = Book.Status.COMPLETE
        book.save(update_fields=["status"])
        return book

    def test_triggers_build_with_preview_flag(self, auth_client, user):
        book = self._book_for(user)
        with patch("books.views.build_book") as mock_task:
            resp = auth_client.post(
                f"/api/books/{book.pk}/build/",
                {"format": "pdf", "preview_structure": True},
                format="json",
            )
        assert resp.status_code == 202
        mock_task.delay.assert_called_once_with(book.pk, preview_structure=True)

    def test_default_is_full_build(self, auth_client, user):
        book = self._book_for(user)
        with patch("books.views.build_book") as mock_task:
            resp = auth_client.post(
                f"/api/books/{book.pk}/build/",
                {"format": "pdf"},
                format="json",
            )
        assert resp.status_code == 202
        mock_task.delay.assert_called_once_with(book.pk, preview_structure=False)

    def test_preview_rejected_with_html_format(self, auth_client, user):
        book = self._book_for(user)
        resp = auth_client.post(
            f"/api/books/{book.pk}/build/",
            {"format": "html", "preview_structure": True},
            format="json",
        )
        assert resp.status_code == 400
        assert b"preview_structure" in resp.content

    def test_preview_skips_html_auto_chain(self, auth_client, user):
        """Even when HTML has been built before, a preview is a single
        build_book.delay call — no chained HTML rebuild."""
        from django.utils import timezone

        book = self._book_for(user)
        book.html_built_at = timezone.now()
        book.save(update_fields=["html_built_at"])

        with (
            patch("books.views.build_book") as mock_pdf,
            patch("books.views.build_book_html") as mock_html,
        ):
            resp = auth_client.post(
                f"/api/books/{book.pk}/build/",
                {"format": "pdf", "preview_structure": True},
                format="json",
            )
        assert resp.status_code == 202
        mock_pdf.delay.assert_called_once_with(book.pk, preview_structure=True)
        mock_html.delay.assert_not_called()
