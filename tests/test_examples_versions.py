"""Tests for the ExampleVersion ledger and its pre_save signal."""

import pytest

from catalog.models import Example, ExampleVersion
from catalog.signals import set_current_user
from tests.factories import ChapterFactory, ExampleFactory


@pytest.mark.django_db
class TestVersionLedger:
    def test_no_version_on_create(self, user, chapter):
        """A newly created example has no version row — the create *is* v1."""
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        assert ExampleVersion.objects.filter(example=ex).count() == 0

    def test_no_version_when_no_tracked_field_changes(self, user, chapter):
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        # Touch only an untracked field (status moves via moderation).
        ex.status = Example.Status.PENDING
        ex.save(update_fields=["status"])
        assert ExampleVersion.objects.filter(example=ex).count() == 0

    def test_version_written_on_statement_change(self, user, chapter):
        ex = ExampleFactory(
            author=user, primary_chapter=chapter, chapters=[chapter],
            statement_tex="Original.",
        )
        ex.statement_tex = "Updated."
        ex.save()
        versions = ExampleVersion.objects.filter(example=ex)
        assert versions.count() == 1
        v = versions.first()
        assert v.version_no == 1
        # Ledger records the PRIOR state.
        assert v.snapshot["statement_tex"] == "Original."

    def test_version_written_on_solution_change(self, user, chapter):
        ex = ExampleFactory(
            author=user, primary_chapter=chapter, chapters=[chapter],
            solution_tex="Original solution.",
        )
        ex.solution_tex = "Updated solution."
        ex.save()
        assert ExampleVersion.objects.filter(example=ex).count() == 1

    def test_version_written_on_difficulty_change(self, user, chapter):
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        ex.difficulty = Example.Difficulty.ADVANCED
        ex.save()
        assert ExampleVersion.objects.filter(example=ex).count() == 1

    def test_version_no_increments(self, user, chapter):
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        ex.statement_tex = "v2"
        ex.save()
        ex.statement_tex = "v3"
        ex.save()
        ex.statement_tex = "v4"
        ex.save()
        nos = list(
            ExampleVersion.objects
            .filter(example=ex)
            .order_by("version_no")
            .values_list("version_no", flat=True)
        )
        assert nos == [1, 2, 3]

    def test_snapshot_records_primary_chapter_chabbr(self, user):
        """Chabbrs (not FK ids) are stored so chapter deletion can't dangle."""
        ch_a = ChapterFactory(chabbr="ALPHA")
        ch_b = ChapterFactory(chabbr="BETA")
        ex = ExampleFactory(
            author=user, primary_chapter=ch_a, chapters=[ch_a],
            statement_tex="v1",
        )
        # Change a tracked field; the snapshot should reference the OLD
        # primary chapter chabbr.
        ex.statement_tex = "v2"
        ex.save()
        v = ExampleVersion.objects.get(example=ex)
        assert v.snapshot["primary_chapter_chabbr"] == "ALPHA"

        # Re-target the primary chapter; another snapshot captures
        # ALPHA again because that was the prior state at this save.
        ex.primary_chapter = ch_b
        ex.chapters.add(ch_b)
        ex.save()
        latest = ExampleVersion.objects.filter(example=ex).order_by("-version_no").first()
        assert latest.snapshot["primary_chapter_chabbr"] == "ALPHA"

    def test_user_attribution_via_thread_local(self, user, chapter):
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        set_current_user(user)
        try:
            ex.statement_tex = "Edited by user."
            ex.save()
        finally:
            set_current_user(None)
        v = ExampleVersion.objects.get(example=ex)
        assert v.created_by_id == user.id

    def test_user_attribution_absent_when_thread_local_unset(self, user, chapter):
        ex = ExampleFactory(author=user, primary_chapter=chapter, chapters=[chapter])
        # No set_current_user — signal should still write a version with null user.
        ex.statement_tex = "No attribution."
        ex.save()
        v = ExampleVersion.objects.get(example=ex)
        assert v.created_by_id is None


@pytest.mark.django_db
class TestVersionThroughAPI:
    """Edits through the author /manage/ endpoint trigger the signal too."""

    def test_published_edit_through_api_writes_version(self, auth_client, user, chapter):
        from catalog.models import Example
        ex = ExampleFactory(
            author=user, primary_chapter=chapter, chapters=[chapter],
            status=Example.Status.PUBLISHED,
            statement_tex="Original published statement.",
        )
        resp = auth_client.patch(
            f"/api/examples/{ex.pk}/manage/",
            {"statement_tex": "Corrected statement."},
            format="json",
        )
        assert resp.status_code == 200
        versions = ExampleVersion.objects.filter(example=ex)
        assert versions.count() == 1
        v = versions.first()
        assert v.snapshot["statement_tex"] == "Original published statement."
        # Through-API edits attribute the version to the request user.
        assert v.created_by_id == user.id

    def test_rejected_edit_through_api_writes_version(self, auth_client, user, chapter):
        ex = ExampleFactory(
            author=user, primary_chapter=chapter, chapters=[chapter],
            status=Example.Status.REJECTED,
            statement_tex="Pre-rejection statement.",
        )
        resp = auth_client.patch(
            f"/api/examples/{ex.pk}/manage/",
            {"statement_tex": "Post-rejection rewrite."},
            format="json",
        )
        assert resp.status_code == 200
        v = ExampleVersion.objects.get(example=ex)
        assert v.snapshot["statement_tex"] == "Pre-rejection statement."
