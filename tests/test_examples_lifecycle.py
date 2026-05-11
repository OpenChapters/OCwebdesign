"""Worked-examples lifecycle tests.

Covers draft → pending → published → rejected transitions, post-publish
re-review-on-edit, the public list/detail endpoints, the author-manage
view's permission rules, and the admin approve/reject workflow.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from catalog.models import Example
from tests.factories import (
    ChapterFactory,
    ExampleFactory,
    PublishedExampleFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestPublicListAndDetail:
    LIST_URL = "/api/examples/"

    def test_anonymous_can_list_published(self, api_client, user):
        ch = ChapterFactory()
        PublishedExampleFactory(author=user, primary_chapter=ch, chapters=[ch])
        resp = api_client.get(self.LIST_URL)
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        assert len(results) == 1

    def test_drafts_not_in_public_list(self, api_client, user):
        ch = ChapterFactory()
        ExampleFactory(author=user, primary_chapter=ch, chapters=[ch])  # draft
        resp = api_client.get(self.LIST_URL)
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        assert results == []

    def test_chapter_filter(self, api_client, user):
        ch_a = ChapterFactory(chabbr="AAA")
        ch_b = ChapterFactory(chabbr="BBB")
        PublishedExampleFactory(author=user, primary_chapter=ch_a, chapters=[ch_a])
        PublishedExampleFactory(author=user, primary_chapter=ch_b, chapters=[ch_b])
        resp = api_client.get(self.LIST_URL, {"chapter": "AAA"})
        results = resp.data.get("results", resp.data)
        assert len(results) == 1
        assert results[0]["primary_chapter"]["chabbr"] == "AAA"

    def test_difficulty_filter(self, api_client, user):
        ch = ChapterFactory()
        PublishedExampleFactory(
            author=user, primary_chapter=ch, chapters=[ch],
            difficulty=Example.Difficulty.ADVANCED,
        )
        PublishedExampleFactory(
            author=user, primary_chapter=ch, chapters=[ch],
            difficulty=Example.Difficulty.INTRODUCTORY,
        )
        resp = api_client.get(self.LIST_URL, {"difficulty": "advanced"})
        results = resp.data.get("results", resp.data)
        assert len(results) == 1
        assert results[0]["difficulty"] == "advanced"

    def test_search_filter(self, api_client, user):
        ch = ChapterFactory()
        PublishedExampleFactory(
            author=user, primary_chapter=ch, chapters=[ch],
            statement_tex="A problem about quaternions.",
        )
        PublishedExampleFactory(
            author=user, primary_chapter=ch, chapters=[ch],
            statement_tex="A problem about Euler angles.",
        )
        resp = api_client.get(self.LIST_URL, {"search": "quaternion"})
        results = resp.data.get("results", resp.data)
        assert len(results) == 1
        assert "quaternion" in results[0]["statement_tex"].lower()

    def test_detail_anonymous_published(self, api_client, published_example):
        resp = api_client.get(f"/api/examples/{published_example.pk}/")
        assert resp.status_code == 200
        # is_own is False for anonymous viewers
        assert resp.data["is_own"] is False

    def test_detail_anonymous_blocked_for_non_published(self, api_client, example):
        resp = api_client.get(f"/api/examples/{example.pk}/")
        assert resp.status_code == 404

    def test_is_own_true_for_author(self, auth_client, published_example):
        resp = auth_client.get(f"/api/examples/{published_example.pk}/")
        assert resp.status_code == 200
        assert resp.data["is_own"] is True

    def test_is_own_false_for_other_user(self, auth_client, user):
        # auth_client is `user`; create a published example by someone else
        other = UserFactory()
        ch = ChapterFactory()
        ex = PublishedExampleFactory(author=other, primary_chapter=ch, chapters=[ch])
        resp = auth_client.get(f"/api/examples/{ex.pk}/")
        assert resp.status_code == 200
        assert resp.data["is_own"] is False


@pytest.mark.django_db
class TestCreate:
    URL = "/api/examples/"

    def _payload(self, chapter):
        return {
            "primary_chapter": chapter.id,
            "chapters": [chapter.id],
            "statement_tex": "Statement.",
            "solution_tex": "Solution.",
            "difficulty": "standard",
        }

    def test_authenticated_create_starts_as_draft(self, auth_client, user):
        ch = ChapterFactory()
        resp = auth_client.post(self.URL, self._payload(ch), format="json")
        assert resp.status_code == 201
        assert resp.data["status"] == "draft"
        assert resp.data["author_display"]  # not empty

    def test_anonymous_create_rejected(self, api_client):
        ch = ChapterFactory()
        resp = api_client.post(self.URL, self._payload(ch), format="json")
        assert resp.status_code == 401

    def test_empty_chapters_rejected(self, auth_client):
        ch = ChapterFactory()
        payload = self._payload(ch)
        payload["chapters"] = []
        resp = auth_client.post(self.URL, payload, format="json")
        assert resp.status_code == 400

    def test_primary_not_in_chapters_rejected(self, auth_client):
        ch_a = ChapterFactory()
        ch_b = ChapterFactory()
        payload = self._payload(ch_a)
        payload["primary_chapter"] = ch_a.id
        payload["chapters"] = [ch_b.id]
        resp = auth_client.post(self.URL, payload, format="json")
        assert resp.status_code == 400

    def test_blank_statement_rejected(self, auth_client):
        ch = ChapterFactory()
        payload = self._payload(ch)
        payload["statement_tex"] = "  "
        resp = auth_client.post(self.URL, payload, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestAuthorManageEdit:
    """The /manage/ PATCH path is what the editor uses on existing rows."""

    def _patch_url(self, pk):
        return f"/api/examples/{pk}/manage/"

    def test_author_edits_draft(self, auth_client, user, chapter):
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        resp = auth_client.patch(
            self._patch_url(ex.pk),
            {"statement_tex": "Updated statement."},
            format="json",
        )
        assert resp.status_code == 200
        ex.refresh_from_db()
        assert ex.statement_tex == "Updated statement."
        assert ex.status == Example.Status.DRAFT  # unchanged

    def test_other_user_cannot_edit(self, auth_client, chapter):
        other = UserFactory()
        ex = ExampleFactory(author=other, primary_chapter=chapter, chapters=[chapter])
        resp = auth_client.patch(
            self._patch_url(ex.pk),
            {"statement_tex": "Hijack."},
            format="json",
        )
        assert resp.status_code == 404
        ex.refresh_from_db()
        assert ex.statement_tex != "Hijack."

    def test_pending_cannot_be_edited(self, auth_client, user, chapter):
        ex = ExampleFactory(
            author=user, primary_chapter=chapter, chapters=[chapter],
            status=Example.Status.PENDING,
        )
        resp = auth_client.patch(
            self._patch_url(ex.pk),
            {"statement_tex": "Edit blocked."},
            format="json",
        )
        assert resp.status_code == 400

    def test_rejected_edit_transitions_to_draft(self, auth_client, user, chapter):
        ex = ExampleFactory(
            author=user, primary_chapter=chapter, chapters=[chapter],
            status=Example.Status.REJECTED,
            rejection_reason="Add a figure.",
        )
        resp = auth_client.patch(
            self._patch_url(ex.pk),
            {"statement_tex": "Now with a figure."},
            format="json",
        )
        assert resp.status_code == 200
        ex.refresh_from_db()
        assert ex.status == Example.Status.DRAFT
        assert ex.rejection_reason == ""

    def test_published_edit_transitions_to_pending(self, auth_client, user, chapter):
        ex = PublishedExampleFactory(
            author=user, primary_chapter=chapter, chapters=[chapter],
        )
        # Simulate a built preview the prior accepted version had.
        ex.preview_built_at = timezone.now()
        ex.preview_build_log = "old log"
        ex.save(update_fields=["preview_built_at", "preview_build_log"])

        resp = auth_client.patch(
            self._patch_url(ex.pk),
            {"statement_tex": "Author correction."},
            format="json",
        )
        assert resp.status_code == 200
        ex.refresh_from_db()
        assert ex.status == Example.Status.PENDING
        assert ex.preview_built_at is None
        assert ex.preview_build_log == ""

    def test_delete_draft(self, auth_client, user, chapter):
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        resp = auth_client.delete(self._patch_url(ex.pk))
        assert resp.status_code == 204
        assert not Example.objects.filter(pk=ex.pk).exists()

    def test_delete_non_draft_blocked(self, auth_client, user, chapter):
        ex = ExampleFactory(
            author=user, primary_chapter=chapter, chapters=[chapter],
            status=Example.Status.PENDING,
        )
        resp = auth_client.delete(self._patch_url(ex.pk))
        assert resp.status_code == 400
        assert Example.objects.filter(pk=ex.pk).exists()


@pytest.mark.django_db
class TestSubmit:
    def _submit_url(self, pk):
        return f"/api/examples/{pk}/submit/"

    def test_submit_requires_fresh_preview(self, auth_client, user, chapter):
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        # no preview_built_at
        resp = auth_client.post(self._submit_url(ex.pk))
        assert resp.status_code == 400

    def test_submit_stale_preview_blocked(self, auth_client, user, chapter):
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        # preview happened before the row's last edit
        ex.preview_built_at = ex.updated_at - timedelta(seconds=10)
        ex.save(update_fields=["preview_built_at"])
        resp = auth_client.post(self._submit_url(ex.pk))
        assert resp.status_code == 400

    def test_submit_happy_path(self, auth_client, user, chapter):
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        # Preview newer than last update: pretend it just finished.
        ex.preview_built_at = ex.updated_at + timedelta(seconds=1)
        ex.save(update_fields=["preview_built_at"])
        resp = auth_client.post(self._submit_url(ex.pk))
        assert resp.status_code == 200
        ex.refresh_from_db()
        assert ex.status == Example.Status.PENDING


@pytest.mark.django_db
class TestAdminApproveReject:
    def _ex_pending(self, user, chapter):
        ex = ExampleFactory(
            author=user, primary_chapter=chapter, chapters=[chapter],
            status=Example.Status.PENDING,
        )
        return ex

    def test_approve_pending(self, staff_client, user, chapter):
        ex = self._ex_pending(user, chapter)
        resp = staff_client.post(f"/api/admin/examples/{ex.pk}/approve/")
        assert resp.status_code == 200
        ex.refresh_from_db()
        assert ex.status == Example.Status.PUBLISHED

    def test_approve_non_pending_blocked(self, staff_client, user, chapter):
        ex = ExampleFactory(
            author=user, primary_chapter=chapter, chapters=[chapter],
            status=Example.Status.DRAFT,
        )
        resp = staff_client.post(f"/api/admin/examples/{ex.pk}/approve/")
        assert resp.status_code == 400

    def test_reject_requires_reason(self, staff_client, user, chapter):
        ex = self._ex_pending(user, chapter)
        resp = staff_client.post(
            f"/api/admin/examples/{ex.pk}/reject/",
            {"rejection_reason": "  "},
            format="json",
        )
        assert resp.status_code == 400

    def test_reject_pending(self, staff_client, user, chapter):
        ex = self._ex_pending(user, chapter)
        resp = staff_client.post(
            f"/api/admin/examples/{ex.pk}/reject/",
            {"rejection_reason": "Clean up notation."},
            format="json",
        )
        assert resp.status_code == 200
        ex.refresh_from_db()
        assert ex.status == Example.Status.REJECTED
        assert ex.rejection_reason == "Clean up notation."

    def test_non_admin_cannot_approve(self, auth_client, user, chapter):
        ex = self._ex_pending(user, chapter)
        resp = auth_client.post(f"/api/admin/examples/{ex.pk}/approve/")
        assert resp.status_code == 403

    def test_admin_delete(self, staff_client, user, chapter):
        ex = ExampleFactory(
            author=user, primary_chapter=chapter, chapters=[chapter],
            status=Example.Status.PUBLISHED,
        )
        resp = staff_client.delete(f"/api/admin/examples/{ex.pk}/")
        assert resp.status_code == 204
        assert not Example.objects.filter(pk=ex.pk).exists()
