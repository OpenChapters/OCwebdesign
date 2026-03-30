"""Tests for the admin API endpoints."""

import pytest

from admin_api.models import AuditEntry, SiteSetting
from books.models import Book
from tests.factories import (
    BookFactory,
    BuildJobFactory,
    ChapterFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestAdminPermissions:
    """All admin endpoints should reject non-staff users."""

    ADMIN_URLS = [
        "/api/admin/dashboard/",
        "/api/admin/workers/",
        "/api/admin/users/",
        "/api/admin/chapters/",
        "/api/admin/builds/",
        "/api/admin/system/health/",
        "/api/admin/settings/",
        "/api/admin/audit/",
    ]

    def test_unauthenticated_rejected(self, api_client):
        for url in self.ADMIN_URLS:
            resp = api_client.get(url)
            assert resp.status_code in (401, 403), f"{url} should reject unauthenticated"

    def test_non_staff_rejected(self, auth_client):
        for url in self.ADMIN_URLS:
            resp = auth_client.get(url)
            assert resp.status_code == 403, f"{url} should reject non-staff"

    def test_staff_allowed(self, staff_client):
        for url in self.ADMIN_URLS:
            resp = staff_client.get(url)
            assert resp.status_code == 200, f"{url} should allow staff"


@pytest.mark.django_db
class TestDashboard:
    def test_returns_stats(self, staff_client):
        UserFactory()
        ChapterFactory()
        BookFactory()
        resp = staff_client.get("/api/admin/dashboard/")
        assert resp.status_code == 200
        assert "users" in resp.data
        assert "chapters" in resp.data
        assert "books" in resp.data
        assert "builds_today" in resp.data
        assert "storage" in resp.data
        assert "recent_builds" in resp.data


@pytest.mark.django_db
class TestAdminUsers:
    def test_list_users(self, staff_client):
        UserFactory()
        UserFactory()
        resp = staff_client.get("/api/admin/users/")
        assert resp.status_code == 200
        assert resp.data["count"] >= 2

    def test_search_users(self, staff_client):
        UserFactory(email="findme@test.com")
        UserFactory(email="other@test.com")
        resp = staff_client.get("/api/admin/users/?search=findme")
        assert resp.data["count"] == 1

    def test_create_user(self, staff_client):
        resp = staff_client.post("/api/admin/users/", {
            "email": "created@test.com",
            "password": "securepass1",
        })
        assert resp.status_code == 201

    def test_update_user(self, staff_client):
        user = UserFactory()
        resp = staff_client.patch(f"/api/admin/users/{user.id}/", {
            "is_active": False,
        })
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.is_active is False

    def test_update_creates_audit_entry(self, staff_client):
        user = UserFactory(is_active=True)
        staff_client.patch(f"/api/admin/users/{user.id}/", {"is_active": False})
        assert AuditEntry.objects.filter(action="user.update", target_id=user.id).exists()

    def test_delete_user(self, staff_client):
        user = UserFactory()
        resp = staff_client.delete(f"/api/admin/users/{user.id}/")
        assert resp.status_code == 204

    def test_cannot_delete_self(self, staff_client, staff_user):
        resp = staff_client.delete(f"/api/admin/users/{staff_user.id}/")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestAdminChapters:
    def test_list_all_chapters(self, staff_client):
        ChapterFactory(published=True)
        ChapterFactory(published=False)
        resp = staff_client.get("/api/admin/chapters/")
        assert resp.data["count"] == 2  # includes unpublished

    def test_update_chapter_metadata(self, staff_client):
        ch = ChapterFactory(description="old")
        resp = staff_client.patch(f"/api/admin/chapters/{ch.id}/", {
            "description": "new description",
        })
        assert resp.status_code == 200
        ch.refresh_from_db()
        assert ch.description == "new description"

    def test_toggle_published(self, staff_client):
        ch = ChapterFactory(published=True)
        resp = staff_client.patch(f"/api/admin/chapters/{ch.id}/", {"published": False})
        assert resp.status_code == 200
        ch.refresh_from_db()
        assert ch.published is False


@pytest.mark.django_db
class TestAdminBuilds:
    def test_list_builds(self, staff_client):
        BuildJobFactory()
        resp = staff_client.get("/api/admin/builds/")
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_build_detail(self, staff_client):
        job = BuildJobFactory(log_output="test log", error_message="test error")
        resp = staff_client.get(f"/api/admin/builds/{job.id}/")
        assert resp.status_code == 200
        assert resp.data["log_output"] == "test log"
        assert resp.data["error_message"] == "test error"

    def test_retry_failed_build(self, staff_client):
        job = BuildJobFactory()
        job.book.status = Book.Status.FAILED
        job.book.save()
        resp = staff_client.post(f"/api/admin/builds/{job.id}/retry/")
        assert resp.status_code == 200
        job.book.refresh_from_db()
        assert job.book.status == Book.Status.QUEUED


@pytest.mark.django_db
class TestAdminSettings:
    def test_get_defaults(self, staff_client):
        resp = staff_client.get("/api/admin/settings/")
        assert resp.status_code == 200
        assert resp.data["site_name"] == "OpenChapters"
        assert resp.data["registration_enabled"] is True

    def test_update_setting(self, staff_client):
        resp = staff_client.patch("/api/admin/settings/", {
            "site_name": "My Platform",
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["settings"]["site_name"] == "My Platform"
        assert SiteSetting.objects.get(key="site_name").value == "My Platform"

    def test_update_creates_audit_entry(self, staff_client):
        staff_client.patch("/api/admin/settings/", {
            "site_name": "Audited",
        }, format="json")
        assert AuditEntry.objects.filter(action="settings.update").exists()


@pytest.mark.django_db
class TestPublicSettings:
    def test_public_settings_unauthenticated(self, api_client):
        resp = api_client.get("/api/settings/public/")
        assert resp.status_code == 200
        assert "site_name" in resp.data
        assert "registration_enabled" in resp.data

    def test_public_settings_reflect_changes(self, staff_client, api_client):
        staff_client.patch("/api/admin/settings/", {
            "announcement_banner": "Maintenance tonight",
        }, format="json")
        resp = api_client.get("/api/settings/public/")
        assert resp.data["announcement_banner"] == "Maintenance tonight"


@pytest.mark.django_db
class TestAuditLog:
    def test_audit_log_initially_empty(self, staff_client):
        resp = staff_client.get("/api/admin/audit/")
        assert resp.status_code == 200
        assert resp.data["count"] == 0

    def test_audit_log_records_actions(self, staff_client):
        user = UserFactory()
        staff_client.patch(f"/api/admin/users/{user.id}/", {"is_staff": True})
        resp = staff_client.get("/api/admin/audit/")
        assert resp.data["count"] >= 1
        actions = [e["action"] for e in resp.data["results"]]
        assert "user.update" in actions
