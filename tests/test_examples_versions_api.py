"""Tests for the ExampleVersion HTTP endpoint
(GET /api/examples/<id>/versions/)."""

import pytest

from catalog.models import Example
from tests.factories import (
    ChapterFactory,
    ExampleFactory,
    ExampleVersionFactory,
    PublishedExampleFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestVersionListEndpoint:
    def _url(self, pk):
        return f"/api/examples/{pk}/versions/"

    def test_author_sees_own_versions(self, auth_client, user, chapter):
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        ExampleVersionFactory(example=ex, version_no=1, snapshot={
            "statement_tex": "v1 statement",
            "solution_tex": "v1 solution",
            "difficulty": "standard",
            "primary_chapter_chabbr": chapter.chabbr,
            "chapters_chabbrs": [chapter.chabbr],
            "status": "draft",
            "slug": None,
        })
        ExampleVersionFactory(example=ex, version_no=2, snapshot={
            "statement_tex": "v2 statement",
            "solution_tex": "v2 solution",
            "difficulty": "standard",
            "primary_chapter_chabbr": chapter.chabbr,
            "chapters_chabbrs": [chapter.chabbr],
            "status": "draft",
            "slug": None,
        })

        resp = auth_client.get(self._url(ex.pk))
        assert resp.status_code == 200
        # Newest first
        versions = resp.data
        assert [v["version_no"] for v in versions] == [2, 1]
        assert versions[0]["snapshot"]["statement_tex"] == "v2 statement"

    def test_snapshot_fields_round_trip(self, auth_client, user, chapter):
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        ExampleVersionFactory(example=ex, version_no=1, snapshot={
            "statement_tex": "prior",
            "solution_tex": "prior soln",
            "difficulty": "advanced",
            "primary_chapter_chabbr": "AAA",
            "chapters_chabbrs": ["AAA", "BBB"],
            "status": "published",
            "slug": None,
        })
        resp = auth_client.get(self._url(ex.pk))
        assert resp.status_code == 200
        snap = resp.data[0]["snapshot"]
        assert snap["statement_tex"] == "prior"
        assert snap["solution_tex"] == "prior soln"
        assert snap["difficulty"] == "advanced"
        assert snap["primary_chapter_chabbr"] == "AAA"
        assert snap["chapters_chabbrs"] == ["AAA", "BBB"]
        assert snap["status"] == "published"

    def test_editor_display_from_created_by(self, auth_client, user, chapter):
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        editor = UserFactory(full_name="Jane Doe")
        ExampleVersionFactory(
            example=ex, version_no=1,
            created_by=editor,
            snapshot={
                "statement_tex": "x", "solution_tex": "y", "difficulty": "standard",
                "primary_chapter_chabbr": None, "chapters_chabbrs": [],
                "status": "draft", "slug": None,
            },
        )
        resp = auth_client.get(self._url(ex.pk))
        assert resp.data[0]["editor_display"] == "Jane Doe"

    def test_editor_display_null_when_unattributed(self, auth_client, user, chapter):
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        ExampleVersionFactory(
            example=ex, version_no=1, created_by=None,
            snapshot={
                "statement_tex": "x", "solution_tex": "y", "difficulty": "standard",
                "primary_chapter_chabbr": None, "chapters_chabbrs": [],
                "status": "draft", "slug": None,
            },
        )
        resp = auth_client.get(self._url(ex.pk))
        assert resp.data[0]["editor_display"] is None

    def test_other_user_gets_404(self, auth_client, chapter):
        # auth_client is fixture `user`. Create an example owned by someone else.
        other = UserFactory()
        ex = ExampleFactory(author=other, primary_chapter=chapter, chapters=[chapter])
        ExampleVersionFactory(example=ex, version_no=1, snapshot={
            "statement_tex": "x", "solution_tex": "y", "difficulty": "standard",
            "primary_chapter_chabbr": None, "chapters_chabbrs": [],
            "status": "draft", "slug": None,
        })
        resp = auth_client.get(self._url(ex.pk))
        # 404, not 403, so the endpoint doesn't leak existence.
        assert resp.status_code == 404

    def test_staff_can_see_any(self, staff_client, chapter):
        other = UserFactory()
        ex = ExampleFactory(author=other, primary_chapter=chapter, chapters=[chapter])
        ExampleVersionFactory(example=ex, version_no=1, snapshot={
            "statement_tex": "x", "solution_tex": "y", "difficulty": "standard",
            "primary_chapter_chabbr": None, "chapters_chabbrs": [],
            "status": "draft", "slug": None,
        })
        resp = staff_client.get(self._url(ex.pk))
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_anonymous_blocked(self, api_client, user, chapter):
        ex = PublishedExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        resp = api_client.get(self._url(ex.pk))
        assert resp.status_code == 401

    def test_missing_example_is_404(self, auth_client):
        resp = auth_client.get(self._url(999_999))
        assert resp.status_code == 404

    def test_empty_history(self, auth_client, user, chapter):
        """An example with no edits yet returns an empty list, not 404."""
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        resp = auth_client.get(self._url(ex.pk))
        assert resp.status_code == 200
        assert resp.data == []
