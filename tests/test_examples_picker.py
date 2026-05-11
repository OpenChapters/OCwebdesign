"""Per-build worked-example picker tests.

Covers Book.excluded_example_ids storage, the validation on PATCH, the
/examples-available/ endpoint that the picker UI reads from, and the
build pipeline's filtering of candidate examples (including silent
tolerance for stale ids).
"""

import pytest

from books.models import Book
from books.tasks import _build_request_data
from tests.factories import (
    BookChapterFactory,
    BookFactory,
    BookPartFactory,
    ChapterFactory,
    PublishedExampleFactory,
    UserFactory,
)


def _count_examples(request_data: dict) -> int:
    return sum(
        len(ch.get("examples") or [])
        for part in request_data.get("parts", [])
        for ch in part.get("chapters", [])
    )


@pytest.mark.django_db
class TestModelDefault:
    def test_default_is_empty_list(self, book):
        assert book.excluded_example_ids == []


@pytest.mark.django_db
class TestPatchValidation:
    def test_patch_happy_path(self, auth_client, book):
        resp = auth_client.patch(
            f"/api/books/{book.id}/",
            {"excluded_example_ids": [10, 11, 12]},
            format="json",
        )
        assert resp.status_code == 200
        book.refresh_from_db()
        assert book.excluded_example_ids == [10, 11, 12]

    def test_patch_dedups_and_preserves_order(self, auth_client, book):
        resp = auth_client.patch(
            f"/api/books/{book.id}/",
            {"excluded_example_ids": [7, 5, 7, 9, 5]},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["excluded_example_ids"] == [7, 5, 9]

    def test_patch_rejects_non_list(self, auth_client, book):
        resp = auth_client.patch(
            f"/api/books/{book.id}/",
            {"excluded_example_ids": "not a list"},
            format="json",
        )
        assert resp.status_code == 400

    def test_patch_rejects_non_int_entries(self, auth_client, book):
        resp = auth_client.patch(
            f"/api/books/{book.id}/",
            {"excluded_example_ids": [1, "two", 3]},
            format="json",
        )
        assert resp.status_code == 400

    def test_patch_rejects_bools(self, auth_client, book):
        # bool is a subclass of int in Python; serializer should reject it.
        resp = auth_client.patch(
            f"/api/books/{book.id}/",
            {"excluded_example_ids": [True, False]},
            format="json",
        )
        assert resp.status_code == 400

    def test_owner_only(self, auth_client):
        other_book = BookFactory()  # different user
        resp = auth_client.patch(
            f"/api/books/{other_book.id}/",
            {"excluded_example_ids": [1]},
            format="json",
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestExamplesAvailableEndpoint:
    def _setup_book_with_examples(self, user):
        ch1 = ChapterFactory(chabbr="CHAP1")
        ch2 = ChapterFactory(chabbr="CHAP2")
        book = BookFactory(user=user)
        part = BookPartFactory(book=book, order=0)
        BookChapterFactory(part=part, chapter=ch1, order=0)
        BookChapterFactory(part=part, chapter=ch2, order=1)
        ex_a = PublishedExampleFactory(primary_chapter=ch1, chapters=[ch1])
        ex_b = PublishedExampleFactory(primary_chapter=ch2, chapters=[ch2])
        # Cross-chapter example tagged to both chapters
        ex_c = PublishedExampleFactory(primary_chapter=ch1, chapters=[ch1, ch2])
        return book, ch1, ch2, ex_a, ex_b, ex_c

    def test_endpoint_groups_by_host(self, auth_client, user):
        book, ch1, ch2, ex_a, ex_b, ex_c = self._setup_book_with_examples(user)
        resp = auth_client.get(f"/api/books/{book.id}/examples-available/")
        assert resp.status_code == 200
        groups = {g["chapter"]["chabbr"]: g for g in resp.data["groups"]}
        # Cross-chapter ex_c goes to CHAP1 (earliest in book)
        chap1_ids = {e["id"] for e in groups["CHAP1"]["examples"]}
        chap2_ids = {e["id"] for e in groups["CHAP2"]["examples"]}
        assert ex_a.id in chap1_ids
        assert ex_c.id in chap1_ids
        assert ex_b.id in chap2_ids
        assert ex_c.id not in chap2_ids
        assert resp.data["excluded_example_ids"] == []

    def test_endpoint_shows_excluded(self, auth_client, user):
        book, _, _, ex_a, _, _ = self._setup_book_with_examples(user)
        book.excluded_example_ids = [ex_a.id]
        book.save(update_fields=["excluded_example_ids"])
        resp = auth_client.get(f"/api/books/{book.id}/examples-available/")
        assert resp.status_code == 200
        assert resp.data["excluded_example_ids"] == [ex_a.id]
        # The example still appears in the available list — the picker
        # uses excluded_example_ids to display state, not to filter the
        # group entries.
        all_ids = {e["id"] for g in resp.data["groups"] for e in g["examples"]}
        assert ex_a.id in all_ids

    def test_endpoint_omits_chapters_with_no_examples(self, auth_client, user):
        ch = ChapterFactory(chabbr="EMPTY")
        book = BookFactory(user=user)
        part = BookPartFactory(book=book, order=0)
        BookChapterFactory(part=part, chapter=ch, order=0)
        resp = auth_client.get(f"/api/books/{book.id}/examples-available/")
        assert resp.status_code == 200
        assert resp.data["groups"] == []

    def test_endpoint_owner_only(self, auth_client):
        other_book = BookFactory()
        resp = auth_client.get(f"/api/books/{other_book.id}/examples-available/")
        assert resp.status_code == 404

    def test_endpoint_unauthenticated(self, api_client, book):
        resp = api_client.get(f"/api/books/{book.id}/examples-available/")
        assert resp.status_code == 401

    def test_excludes_non_published(self, auth_client, user):
        from catalog.models import Example
        from tests.factories import ExampleFactory

        ch = ChapterFactory(chabbr="ABC")
        book = BookFactory(user=user)
        part = BookPartFactory(book=book, order=0)
        BookChapterFactory(part=part, chapter=ch, order=0)
        # Draft/pending/rejected should NOT appear.
        ExampleFactory(primary_chapter=ch, chapters=[ch], status=Example.Status.DRAFT)
        ExampleFactory(primary_chapter=ch, chapters=[ch], status=Example.Status.PENDING)
        ExampleFactory(primary_chapter=ch, chapters=[ch], status=Example.Status.REJECTED)
        PublishedExampleFactory(primary_chapter=ch, chapters=[ch])
        resp = auth_client.get(f"/api/books/{book.id}/examples-available/")
        assert resp.status_code == 200
        groups = resp.data["groups"]
        # Only the one published example
        assert len(groups) == 1
        assert len(groups[0]["examples"]) == 1


@pytest.mark.django_db
class TestBuildPipelineFiltering:
    """The picker is meaningful only if _build_request_data honors it."""

    def _book_with_two_examples(self, user):
        ch = ChapterFactory(chabbr="QQQ", github_repo="OpenChapters/OpenChapters")
        book = BookFactory(user=user)
        part = BookPartFactory(book=book, order=0)
        BookChapterFactory(part=part, chapter=ch, order=0)
        ex_keep = PublishedExampleFactory(primary_chapter=ch, chapters=[ch])
        ex_excl = PublishedExampleFactory(primary_chapter=ch, chapters=[ch])
        return book, ex_keep, ex_excl

    def test_no_exclusions_includes_everything(self, user):
        book, ex_keep, ex_excl = self._book_with_two_examples(user)
        data = _build_request_data(book)
        assert _count_examples(data) == 2

    def test_excluded_example_omitted(self, user):
        book, ex_keep, ex_excl = self._book_with_two_examples(user)
        book.excluded_example_ids = [ex_excl.id]
        book.save(update_fields=["excluded_example_ids"])
        data = _build_request_data(book)
        kept = [
            e["id"]
            for p in data["parts"]
            for c in p["chapters"]
            for e in c.get("examples", [])
        ]
        assert kept == [ex_keep.id]

    def test_stale_excluded_id_tolerated(self, user):
        """A non-existent id in excluded_example_ids must not crash."""
        book, ex_keep, ex_excl = self._book_with_two_examples(user)
        book.excluded_example_ids = [ex_excl.id, 999_999]
        book.save(update_fields=["excluded_example_ids"])
        data = _build_request_data(book)
        kept = [
            e["id"]
            for p in data["parts"]
            for c in p["chapters"]
            for e in c.get("examples", [])
        ]
        assert kept == [ex_keep.id]

    def test_include_examples_false_overrides_picker(self, user):
        book, ex_keep, ex_excl = self._book_with_two_examples(user)
        book.include_examples = False
        book.save(update_fields=["include_examples"])
        data = _build_request_data(book)
        assert _count_examples(data) == 0

    def test_excluded_solo_keeps_others(self, user):
        """One book may exclude an example without affecting another book."""
        other_user = UserFactory()
        book_a, ex_keep, ex_excl = self._book_with_two_examples(user)
        # Build a second book sharing one chapter
        ch = book_a.parts.first().book_chapters.first().chapter
        book_b = BookFactory(user=other_user)
        part_b = BookPartFactory(book=book_b, order=0)
        BookChapterFactory(part=part_b, chapter=ch, order=0)

        book_a.excluded_example_ids = [ex_excl.id]
        book_a.save(update_fields=["excluded_example_ids"])

        data_a = _build_request_data(book_a)
        data_b = _build_request_data(book_b)
        assert _count_examples(data_a) == 1
        assert _count_examples(data_b) == 2
