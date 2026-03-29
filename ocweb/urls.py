from pathlib import Path

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from users.token import CustomTokenObtainPairView

from books.views import (
    BookDetailView,
    BookListCreateView,
    BuildStatusView,
    BuildTriggerView,
    CoverImageView,
    DownloadPDFByTokenView,
    DownloadPDFView,
    LibraryView,
    PartReorderView,
    PartChapterDetailView,
    PartChapterListCreateView,
    PartChapterReorderView,
    PartDetailView,
    PartListCreateView,
)
from catalog.views import ChapterCoverView, ChapterDetailView, ChapterListView
from users.views import (
    ChangePasswordView,
    ForgotPasswordView,
    ProfileView,
    RegisterView,
    ResetPasswordView,
    TurnstileConfigView,
)

def about_md(request):
    """Serve docs/About.md as plain text for the frontend to render."""
    md_path = Path(__file__).resolve().parent.parent / "docs" / "About.md"
    if md_path.is_file():
        return HttpResponse(md_path.read_text(), content_type="text/plain; charset=utf-8")
    return HttpResponse("# About\n\nContent not available.", content_type="text/plain; charset=utf-8")


def user_guide_md(request):
    """Serve docs/user-guide.md as plain text for the frontend to render."""
    md_path = Path(__file__).resolve().parent.parent / "docs" / "user-guide.md"
    if md_path.is_file():
        return HttpResponse(md_path.read_text(), content_type="text/plain; charset=utf-8")
    return HttpResponse("# User Guide\n\nContent not available.", content_type="text/plain; charset=utf-8")


urlpatterns = [
    path("admin/", admin.site.urls),

    # ── Auth ──────────────────────────────────────────────────────────────────
    path("api/auth/register/", RegisterView.as_view(), name="auth-register"),
    path("api/auth/turnstile/", TurnstileConfigView.as_view(), name="auth-turnstile"),
    path("api/auth/login/", CustomTokenObtainPairView.as_view(), name="auth-login"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("api/auth/forgot-password/", ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("api/auth/reset-password/", ResetPasswordView.as_view(), name="auth-reset-password"),
    path("api/auth/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("api/auth/profile/", ProfileView.as_view(), name="auth-profile"),

    # ── Catalog ───────────────────────────────────────────────────────────────
    path("api/chapters/", ChapterListView.as_view(), name="chapter-list"),
    path("api/chapters/<int:pk>/", ChapterDetailView.as_view(), name="chapter-detail"),
    path("api/chapters/<int:pk>/cover/", ChapterCoverView.as_view(), name="chapter-cover"),

    # ── Books ─────────────────────────────────────────────────────────────────
    path("api/books/", BookListCreateView.as_view(), name="book-list"),
    path("api/books/<int:pk>/", BookDetailView.as_view(), name="book-detail"),
    path("api/books/<int:book_pk>/cover/", CoverImageView.as_view(), name="book-cover"),

    # Parts
    path("api/books/<int:book_pk>/parts/", PartListCreateView.as_view(), name="part-list"),
    path("api/books/<int:book_pk>/parts/<int:part_pk>/", PartDetailView.as_view(), name="part-detail"),
    path("api/books/<int:book_pk>/parts/reorder/", PartReorderView.as_view(), name="part-reorder"),

    # Chapters within a part
    path(
        "api/books/<int:book_pk>/parts/<int:part_pk>/chapters/",
        PartChapterListCreateView.as_view(),
        name="part-chapter-list",
    ),
    path(
        "api/books/<int:book_pk>/parts/<int:part_pk>/chapters/reorder/",
        PartChapterReorderView.as_view(),
        name="part-chapter-reorder",
    ),
    path(
        "api/books/<int:book_pk>/parts/<int:part_pk>/chapters/<int:chapter_pk>/",
        PartChapterDetailView.as_view(),
        name="part-chapter-detail",
    ),

    # Build
    path("api/books/<int:book_pk>/build/", BuildTriggerView.as_view(), name="build-trigger"),
    path("api/books/<int:book_pk>/build/status/", BuildStatusView.as_view(), name="build-status"),
    path("api/books/<int:book_pk>/download/", DownloadPDFView.as_view(), name="download-pdf"),

    # ── Library ───────────────────────────────────────────────────────────────
    path("api/library/", LibraryView.as_view(), name="library"),

    # ── Admin API ──────────────────────────────────────────────────────────────
    path("api/admin/", include("admin_api.urls")),

    # ── Public settings (no auth) ────────────────────────────────────────────
    path("api/settings/public/", __import__("admin_api.views", fromlist=["PublicSettingsView"]).PublicSettingsView.as_view(), name="public-settings"),

    # ── Signed PDF download (from email links, no auth required) ────────────
    path("api/dl/<str:token>/", DownloadPDFByTokenView.as_view(), name="download-pdf-token"),

    # ── About (serves markdown for frontend rendering) ────────────────────────
    path("api/about/", about_md, name="about"),
    path("api/user-guide/", user_guide_md, name="user-guide"),
]
