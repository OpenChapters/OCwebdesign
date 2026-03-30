"""Tests for the chapter catalog API."""

import pytest

from tests.factories import ChapterFactory, FoundationalChapterFactory


@pytest.mark.django_db
class TestChapterList:
    URL = "/api/chapters/"

    def test_list_published_chapters(self, api_client):
        ChapterFactory(published=True, title="Published")
        ChapterFactory(published=False, title="Unpublished")
        resp = api_client.get(self.URL)
        assert resp.status_code == 200
        titles = [c["title"] for c in resp.data["results"]]
        assert "Published" in titles
        assert "Unpublished" not in titles

    def test_list_includes_all_fields(self, api_client):
        ChapterFactory()
        resp = api_client.get(self.URL)
        ch = resp.data["results"][0]
        for field in ["id", "title", "authors", "toc", "chapter_type", "chabbr", "depends_on"]:
            assert field in ch

    def test_pagination(self, api_client):
        for i in range(55):
            ChapterFactory()
        resp = api_client.get(self.URL)
        assert resp.data["count"] == 55
        assert len(resp.data["results"]) == 50  # PAGE_SIZE
        assert resp.data["next"] is not None

    def test_unauthenticated_access(self, api_client):
        """Chapter list is public — no auth required."""
        resp = api_client.get(self.URL)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestChapterDetail:
    def test_get_published_chapter(self, api_client, chapter):
        resp = api_client.get(f"/api/chapters/{chapter.id}/")
        assert resp.status_code == 200
        assert resp.data["title"] == chapter.title

    def test_get_unpublished_chapter(self, api_client):
        ch = ChapterFactory(published=False)
        resp = api_client.get(f"/api/chapters/{ch.id}/")
        assert resp.status_code == 404

    def test_get_nonexistent_chapter(self, api_client):
        resp = api_client.get("/api/chapters/99999/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestChapterTypes:
    def test_topical_and_foundational(self, api_client):
        ChapterFactory(chapter_type="topical", title="Topical")
        FoundationalChapterFactory(title="Foundational")
        resp = api_client.get("/api/chapters/")
        types = {c["title"]: c["chapter_type"] for c in resp.data["results"]}
        assert types["Topical"] == "topical"
        assert types["Foundational"] == "foundational"

    def test_depends_on_field(self, api_client):
        fc = FoundationalChapterFactory(chabbr="LINALG")
        tc = ChapterFactory(depends_on=["LINALG"])
        resp = api_client.get(f"/api/chapters/{tc.id}/")
        assert resp.data["depends_on"] == ["LINALG"]
