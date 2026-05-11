"""Account deletion 7-day grace period (critical-look §4 item 15)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from users.tasks import purge_expired_accounts
from tests.factories import UserFactory


@pytest.mark.django_db
class TestScheduleDeletion:
    URL = "/api/auth/profile/"

    def test_delete_schedules_instead_of_purging(self, auth_client, user):
        assert user.deletion_scheduled_at is None
        resp = auth_client.delete(self.URL)
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.deletion_scheduled_at is not None
        # Window is 7 days; allow a few seconds of clock slack.
        delta = user.deletion_scheduled_at - timezone.now()
        assert timedelta(days=6, hours=23) < delta <= timedelta(days=7, seconds=10)

    def test_delete_is_idempotent(self, auth_client, user):
        """Calling DELETE twice should not push the deletion date forward."""
        resp1 = auth_client.delete(self.URL)
        scheduled_first = resp1.data["deletion_scheduled_at"]
        resp2 = auth_client.delete(self.URL)
        scheduled_second = resp2.data["deletion_scheduled_at"]
        assert scheduled_first == scheduled_second

    def test_profile_exposes_deletion_scheduled_at(self, auth_client, user):
        resp = auth_client.get(self.URL)
        assert resp.status_code == 200
        assert "deletion_scheduled_at" in resp.data
        assert resp.data["deletion_scheduled_at"] is None

    def test_anonymous_cannot_delete(self, api_client):
        resp = api_client.delete(self.URL)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestCancelDeletion:
    URL = "/api/auth/profile/cancel-deletion/"

    def test_cancel_clears_field(self, auth_client, user):
        user.deletion_scheduled_at = timezone.now() + timedelta(days=7)
        user.save(update_fields=["deletion_scheduled_at"])
        resp = auth_client.post(self.URL)
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.deletion_scheduled_at is None

    def test_cancel_is_noop_when_nothing_scheduled(self, auth_client, user):
        resp = auth_client.post(self.URL)
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.deletion_scheduled_at is None

    def test_anonymous_cannot_cancel(self, api_client):
        resp = api_client.post(self.URL)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestPurgeTask:
    def test_purge_removes_expired(self, user):
        from users.models import User

        user.deletion_scheduled_at = timezone.now() - timedelta(seconds=1)
        user.save(update_fields=["deletion_scheduled_at"])

        count = purge_expired_accounts()
        assert count == 1
        assert not User.objects.filter(pk=user.pk).exists()

    def test_purge_skips_future(self, user):
        from users.models import User

        user.deletion_scheduled_at = timezone.now() + timedelta(days=1)
        user.save(update_fields=["deletion_scheduled_at"])

        count = purge_expired_accounts()
        assert count == 0
        assert User.objects.filter(pk=user.pk).exists()

    def test_purge_skips_unscheduled(self, user):
        from users.models import User

        count = purge_expired_accounts()
        assert count == 0
        assert User.objects.filter(pk=user.pk).exists()

    def test_purge_removes_only_expired_among_many(self):
        """Mixed cohort: one expired, one future-scheduled, one unscheduled."""
        from users.models import User

        u_expired = UserFactory()
        u_expired.deletion_scheduled_at = timezone.now() - timedelta(minutes=5)
        u_expired.save(update_fields=["deletion_scheduled_at"])

        u_future = UserFactory()
        u_future.deletion_scheduled_at = timezone.now() + timedelta(days=3)
        u_future.save(update_fields=["deletion_scheduled_at"])

        u_keep = UserFactory()

        count = purge_expired_accounts()
        assert count == 1
        assert not User.objects.filter(pk=u_expired.pk).exists()
        assert User.objects.filter(pk=u_future.pk).exists()
        assert User.objects.filter(pk=u_keep.pk).exists()
