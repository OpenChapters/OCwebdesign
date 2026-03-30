"""Tests for book CRUD, parts, chapters, reorder, and build trigger."""

import pytest

from books.models import Book, BookChapter, BookPart
from tests.factories import (
    BookChapterFactory,
    BookFactory,
    BookPartFactory,
    ChapterFactory,
)


@pytest.mark.django_db
class TestBookCRUD:
    URL = "/api/books/"

    def test_create_book(self, auth_client, user):
        resp = auth_client.post(self.URL, {"title": "My Book"})
        assert resp.status_code == 201
        assert resp.data["title"] == "My Book"
        assert resp.data["status"] == "draft"
        assert Book.objects.filter(user=user, title="My Book").exists()

    def test_list_own_books(self, auth_client, user):
        BookFactory(user=user, title="Mine")
        BookFactory(title="Not Mine")  # different user
        resp = auth_client.get(self.URL)
        assert resp.status_code == 200
        # API returns paginated or flat list
        books = resp.data if isinstance(resp.data, list) else resp.data.get("results", resp.data)
        titles = [b["title"] for b in books]
        assert "Mine" in titles
        assert "Not Mine" not in titles

    def test_get_book_detail(self, auth_client, book):
        resp = auth_client.get(f"{self.URL}{book.id}/")
        assert resp.status_code == 200
        assert resp.data["title"] == book.title
        assert "parts" in resp.data

    def test_update_book_title(self, auth_client, book):
        resp = auth_client.patch(f"{self.URL}{book.id}/", {"title": "New Title"})
        assert resp.status_code == 200
        book.refresh_from_db()
        assert book.title == "New Title"

    def test_update_book_doi(self, auth_client, book):
        resp = auth_client.patch(f"{self.URL}{book.id}/", {"doi": "10.1234/test"})
        assert resp.status_code == 200
        book.refresh_from_db()
        assert book.doi == "10.1234/test"

    def test_delete_book(self, auth_client, book):
        resp = auth_client.delete(f"{self.URL}{book.id}/")
        assert resp.status_code == 204
        assert not Book.objects.filter(pk=book.pk).exists()

    def test_cannot_access_other_users_book(self, auth_client):
        other_book = BookFactory()  # different user
        resp = auth_client.get(f"{self.URL}{other_book.id}/")
        assert resp.status_code == 404

    def test_unauthenticated_access(self, api_client):
        resp = api_client.get(self.URL)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestParts:
    def test_add_part(self, auth_client, book):
        resp = auth_client.post(f"/api/books/{book.id}/parts/", {
            "title": "Part I",
            "order": 0,
        })
        assert resp.status_code == 201
        assert BookPart.objects.filter(book=book, title="Part I").exists()

    def test_rename_part(self, auth_client, book):
        part = BookPartFactory(book=book, order=0)
        resp = auth_client.patch(f"/api/books/{book.id}/parts/{part.id}/", {
            "title": "Renamed",
        })
        assert resp.status_code == 200
        part.refresh_from_db()
        assert part.title == "Renamed"

    def test_delete_part(self, auth_client, book):
        part = BookPartFactory(book=book, order=0)
        resp = auth_client.delete(f"/api/books/{book.id}/parts/{part.id}/")
        assert resp.status_code == 204
        assert not BookPart.objects.filter(pk=part.pk).exists()

    def test_reorder_parts(self, auth_client, book):
        p1 = BookPartFactory(book=book, title="First", order=0)
        p2 = BookPartFactory(book=book, title="Second", order=1)
        resp = auth_client.patch(f"/api/books/{book.id}/parts/reorder/", {
            "order": [p2.id, p1.id],
        }, format="json")
        assert resp.status_code == 200
        p1.refresh_from_db()
        p2.refresh_from_db()
        assert p2.order < p1.order


@pytest.mark.django_db
class TestBookChapters:
    def test_add_chapter_to_part(self, auth_client, book):
        part = BookPartFactory(book=book, order=0)
        chapter = ChapterFactory()
        resp = auth_client.post(
            f"/api/books/{book.id}/parts/{part.id}/chapters/",
            {"chapter_id": chapter.id, "order": 0},
        )
        assert resp.status_code == 201
        assert BookChapter.objects.filter(part=part, chapter=chapter).exists()

    def test_remove_chapter(self, auth_client, book):
        part = BookPartFactory(book=book, order=0)
        bc = BookChapterFactory(part=part, order=0)
        resp = auth_client.delete(
            f"/api/books/{book.id}/parts/{part.id}/chapters/{bc.id}/"
        )
        assert resp.status_code == 204
        assert not BookChapter.objects.filter(pk=bc.pk).exists()

    def test_reorder_chapters(self, auth_client, book):
        part = BookPartFactory(book=book, order=0)
        bc1 = BookChapterFactory(part=part, order=0)
        bc2 = BookChapterFactory(part=part, order=1)
        resp = auth_client.patch(
            f"/api/books/{book.id}/parts/{part.id}/chapters/reorder/",
            {"order": [bc2.id, bc1.id]},
            format="json",
        )
        assert resp.status_code == 200
        bc1.refresh_from_db()
        bc2.refresh_from_db()
        assert bc2.order < bc1.order


@pytest.mark.django_db
class TestBuildTrigger:
    def test_trigger_build(self, auth_client, book):
        part = BookPartFactory(book=book, order=0)
        BookChapterFactory(part=part, order=0)
        resp = auth_client.post(f"/api/books/{book.id}/build/")
        assert resp.status_code == 202
        book.refresh_from_db()
        assert book.status == Book.Status.QUEUED

    def test_trigger_build_empty_book(self, auth_client, book):
        """Books with no chapters can still be queued (pipeline will fail)."""
        resp = auth_client.post(f"/api/books/{book.id}/build/")
        assert resp.status_code == 202

    def test_cannot_trigger_while_building(self, auth_client, book):
        book.status = Book.Status.BUILDING
        book.save()
        resp = auth_client.post(f"/api/books/{book.id}/build/")
        assert resp.status_code == 409

    def test_cannot_trigger_while_queued(self, auth_client, book):
        book.status = Book.Status.QUEUED
        book.save()
        resp = auth_client.post(f"/api/books/{book.id}/build/")
        assert resp.status_code == 409

    def test_atomic_build_trigger(self, auth_client, book):
        """Second concurrent trigger should fail."""
        part = BookPartFactory(book=book, order=0)
        BookChapterFactory(part=part, order=0)
        resp1 = auth_client.post(f"/api/books/{book.id}/build/")
        assert resp1.status_code == 202
        resp2 = auth_client.post(f"/api/books/{book.id}/build/")
        assert resp2.status_code == 409
