"""Tests for the SiteConfig singleton and its surfacing through
the public-settings endpoint."""

import pytest

from admin_api.models import SiteConfig


@pytest.mark.django_db
class TestSiteConfigModel:
    def test_load_creates_singleton_when_missing(self):
        assert SiteConfig.objects.count() == 0
        config = SiteConfig.load()
        assert config.pk == 1
        assert SiteConfig.objects.count() == 1

    def test_load_returns_existing_row(self):
        SiteConfig.load()
        config = SiteConfig.load()
        assert config.pk == 1
        assert SiteConfig.objects.count() == 1

    def test_save_forces_pk_one(self):
        # Even if a caller tries to create a second row, save() pins to pk=1.
        c = SiteConfig(splash_enabled=True)
        c.save()
        assert c.pk == 1
        c2 = SiteConfig(splash_enabled=False)
        c2.save()
        assert c2.pk == 1
        assert SiteConfig.objects.count() == 1
        # The second save overwrites the first.
        assert SiteConfig.objects.get(pk=1).splash_enabled is False

    def test_defaults(self):
        config = SiteConfig.load()
        assert config.splash_enabled is False
        assert config.splash_duration_ms == 10000
        assert config.splash_caption == ""
        assert not config.splash_image  # blank/null ImageField is falsy


@pytest.mark.django_db
class TestPublicSettingsSplashFields:
    """The /api/settings/public/ endpoint must surface SiteConfig splash fields."""

    def test_returns_defaults_when_no_config_row(self, api_client):
        assert SiteConfig.objects.count() == 0
        resp = api_client.get("/api/settings/public/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["splash_enabled"] is False
        assert data["splash_duration_ms"] == 10000
        assert data["splash_image_url"] is None
        assert data["splash_caption"] == ""
        # Endpoint should have created the singleton via SiteConfig.load().
        assert SiteConfig.objects.count() == 1

    def test_reflects_enabled_config(self, api_client):
        config = SiteConfig.load()
        config.splash_enabled = True
        config.splash_duration_ms = 8000
        config.splash_caption = "Welcome to OpenChapters."
        config.save()
        resp = api_client.get("/api/settings/public/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["splash_enabled"] is True
        assert data["splash_duration_ms"] == 8000
        assert data["splash_caption"] == "Welcome to OpenChapters."

    def test_cache_control_header_set(self, api_client):
        resp = api_client.get("/api/settings/public/")
        assert resp.status_code == 200
        assert "max-age=60" in resp["Cache-Control"]

    def test_no_auth_required(self, api_client):
        # APIClient with no credentials must still get 200.
        resp = api_client.get("/api/settings/public/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestAdminSiteConfigEndpoint:
    """The /api/admin/site-config/ endpoint is staff-only and supports
    JSON + multipart for image upload."""

    def test_anonymous_blocked(self, api_client):
        resp = api_client.get("/api/admin/site-config/")
        assert resp.status_code in (401, 403)

    def test_non_staff_blocked(self, auth_client):
        resp = auth_client.get("/api/admin/site-config/")
        assert resp.status_code == 403

    def test_staff_can_read(self, staff_client):
        resp = staff_client.get("/api/admin/site-config/")
        assert resp.status_code == 200
        data = resp.json()
        assert "splash_enabled" in data
        assert "splash_duration_ms" in data
        assert "splash_image_url" in data
        assert "splash_caption" in data

    def test_staff_can_patch_toggle(self, staff_client):
        resp = staff_client.patch(
            "/api/admin/site-config/",
            data={"splash_enabled": True, "splash_caption": "Hello"},
            format="json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["splash_enabled"] is True
        assert data["splash_caption"] == "Hello"
        # Reading back the public endpoint confirms persistence.
        public = staff_client.get("/api/settings/public/")
        assert public.json()["splash_enabled"] is True

    def test_duration_validated(self, staff_client):
        resp = staff_client.patch(
            "/api/admin/site-config/",
            data={"splash_duration_ms": 500},
            format="json",
        )
        assert resp.status_code == 400
        resp = staff_client.patch(
            "/api/admin/site-config/",
            data={"splash_duration_ms": 1_000_000},
            format="json",
        )
        assert resp.status_code == 400

    def test_clear_image_when_none_is_noop(self, staff_client):
        resp = staff_client.patch(
            "/api/admin/site-config/",
            data={"clear_image": True},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["splash_image_url"] is None
