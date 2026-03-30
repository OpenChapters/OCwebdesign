"""Tests for authentication: registration, login, password reset, profile."""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestRegistration:
    URL = "/api/auth/register/"

    def test_register_success(self, api_client):
        resp = api_client.post(self.URL, {
            "email": "new@test.com",
            "full_name": "New User",
            "password": "securepass1",
            "turnstile_token": "test-token",
        })
        assert resp.status_code == 201
        assert User.objects.filter(email="new@test.com").exists()
        user = User.objects.get(email="new@test.com")
        assert user.full_name == "New User"

    def test_register_short_password(self, api_client):
        resp = api_client.post(self.URL, {
            "email": "new@test.com",
            "full_name": "Test",
            "password": "short",
            "turnstile_token": "test-token",
        })
        assert resp.status_code == 400

    def test_register_duplicate_email(self, api_client, user):
        resp = api_client.post(self.URL, {
            "email": user.email,
            "full_name": "Dup",
            "password": "securepass1",
            "turnstile_token": "test-token",
        })
        assert resp.status_code == 400

    def test_register_missing_turnstile(self, api_client):
        resp = api_client.post(self.URL, {
            "email": "new@test.com",
            "full_name": "Test",
            "password": "securepass1",
        })
        assert resp.status_code == 400


@pytest.mark.django_db
class TestLogin:
    URL = "/api/auth/login/"

    def test_login_success(self, api_client, user):
        resp = api_client.post(self.URL, {
            "email": user.email,
            "password": "testpass123",
        })
        assert resp.status_code == 200
        assert "access" in resp.data
        assert "refresh" in resp.data

    def test_login_wrong_password(self, api_client, user):
        resp = api_client.post(self.URL, {
            "email": user.email,
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, api_client):
        resp = api_client.post(self.URL, {
            "email": "nobody@test.com",
            "password": "testpass123",
        })
        assert resp.status_code == 401

    def test_login_includes_is_staff(self, api_client, staff_user):
        """JWT should include is_staff claim."""
        resp = api_client.post(self.URL, {
            "email": staff_user.email,
            "password": "testpass123",
        })
        assert resp.status_code == 200
        # Decode the token to check is_staff
        import json, base64
        payload = json.loads(base64.b64decode(resp.data["access"].split(".")[1] + "=="))
        assert payload["is_staff"] is True


@pytest.mark.django_db
class TestProfile:
    URL = "/api/auth/profile/"

    def test_get_profile(self, auth_client, user):
        resp = auth_client.get(self.URL)
        assert resp.status_code == 200
        assert resp.data["email"] == user.email
        assert "full_name" in resp.data

    def test_update_full_name(self, auth_client, user):
        resp = auth_client.patch(self.URL, {"full_name": "Updated Name"})
        assert resp.status_code == 200
        assert resp.data["full_name"] == "Updated Name"
        user.refresh_from_db()
        assert user.full_name == "Updated Name"

    def test_delete_account(self, auth_client, user):
        resp = auth_client.delete(self.URL)
        assert resp.status_code == 204
        assert not User.objects.filter(pk=user.pk).exists()

    def test_unauthenticated_profile(self, api_client):
        resp = api_client.get(self.URL)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestChangePassword:
    URL = "/api/auth/change-password/"

    def test_change_password_success(self, auth_client, user):
        resp = auth_client.post(self.URL, {
            "current_password": "testpass123",
            "new_password": "newpass456!",
        })
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.check_password("newpass456!")

    def test_wrong_current_password(self, auth_client):
        resp = auth_client.post(self.URL, {
            "current_password": "wrongpass",
            "new_password": "newpass456!",
        })
        assert resp.status_code == 400

    def test_short_new_password(self, auth_client):
        resp = auth_client.post(self.URL, {
            "current_password": "testpass123",
            "new_password": "short",
        })
        assert resp.status_code == 400


@pytest.mark.django_db
class TestForgotPassword:
    URL = "/api/auth/forgot-password/"

    def test_forgot_password_existing_user(self, api_client, user):
        resp = api_client.post(self.URL, {"email": user.email})
        assert resp.status_code == 200
        # Always returns success (no email enumeration)

    def test_forgot_password_nonexistent_user(self, api_client):
        resp = api_client.post(self.URL, {"email": "nobody@test.com"})
        assert resp.status_code == 200  # Same response to prevent enumeration


@pytest.mark.django_db
class TestResetPassword:
    URL = "/api/auth/reset-password/"

    def test_reset_with_valid_token(self, api_client, user):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        resp = api_client.post(self.URL, {
            "uid": uid,
            "token": token,
            "password": "brandnew123",
        })
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.check_password("brandnew123")

    def test_reset_with_invalid_token(self, api_client, user):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        resp = api_client.post(self.URL, {
            "uid": uid,
            "token": "invalid-token",
            "password": "brandnew123",
        })
        assert resp.status_code == 400
