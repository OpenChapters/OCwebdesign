import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .serializers import RegisterSerializer

logger = logging.getLogger(__name__)
User = get_user_model()


class TurnstileConfigView(APIView):
    """GET /api/auth/turnstile/ — return the Turnstile site key for the frontend widget."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"site_key": getattr(settings, "TURNSTILE_SITE_KEY", "")})


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Account created."}, status=status.HTTP_201_CREATED)


# ── Password Reset ────────────────────────────────────────────────────────────

def _send_reset_email(user, reset_url):
    """Queue password reset email via Celery for retry support."""
    from users.tasks import send_reset_email_task
    send_reset_email_task.delay(user.email, reset_url)


class ForgotPasswordView(APIView):
    """POST /api/auth/forgot-password/ — request a password reset link."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        email = request.data.get("email", "").strip()
        # Always return success to avoid email enumeration
        response = {"detail": "If that email exists, a reset link has been sent."}

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(response)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        site_url = getattr(settings, "SITE_URL", "http://localhost:5173").rstrip("/")
        reset_url = f"{site_url}/reset-password/{uid}/{token}"

        _send_reset_email(user, reset_url)
        return Response(response)


class ResetPasswordView(APIView):
    """POST /api/auth/reset-password/ — set a new password using a reset token."""

    permission_classes = [AllowAny]

    def post(self, request):
        uid = request.data.get("uid", "")
        token = request.data.get("token", "")
        password = request.data.get("password", "")

        if not password or len(password) < 8:
            return Response(
                {"detail": "Password must be at least 8 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (ValueError, User.DoesNotExist):
            return Response(
                {"detail": "Invalid reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {"detail": "Reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save()
        return Response({"detail": "Password has been reset. You can now sign in."})


# ── Profile ───────────────────────────────────────────────────────────────────

class ChangePasswordView(APIView):
    """POST /api/auth/change-password/ — change password while logged in."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        current = request.data.get("current_password", "")
        new_pw = request.data.get("new_password", "")

        if not request.user.check_password(current):
            return Response(
                {"detail": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(new_pw) < 8:
            return Response(
                {"detail": "New password must be at least 8 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_password(new_pw)
        request.user.save()
        return Response({"detail": "Password changed."})


class ProfileView(APIView):
    """GET /api/auth/profile/ — current user info.
    PATCH /api/auth/profile/ — update profile fields.
    DELETE /api/auth/profile/ — delete own account."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "is_staff": u.is_staff,
            "date_joined": u.date_joined,
            "last_login": u.last_login,
        })

    def patch(self, request):
        u = request.user
        full_name = request.data.get("full_name")
        if full_name is not None:
            u.full_name = full_name
            u.save(update_fields=["full_name"])
        return Response({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "is_staff": u.is_staff,
            "date_joined": u.date_joined,
            "last_login": u.last_login,
        })

    def delete(self, request):
        request.user.delete()
        return Response({"detail": "Account deleted."}, status=status.HTTP_204_NO_CONTENT)
