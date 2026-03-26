from pathlib import Path

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from books.views import (
    BookDetailView,
    BookListCreateView,
    BuildStatusView,
    BuildTriggerView,
    DownloadPDFByTokenView,
    DownloadPDFView,
    LibraryView,
    PartChapterDetailView,
    PartChapterListCreateView,
    PartChapterReorderView,
    PartDetailView,
    PartListCreateView,
)
from catalog.views import ChapterDetailView, ChapterListView
from users.views import RegisterView, TurnstileConfigView

def about_md(request):
    """Serve docs/About.md as plain text for the frontend to render."""
    md_path = Path(__file__).resolve().parent.parent / "docs" / "About.md"
    if md_path.is_file():
        return HttpResponse(md_path.read_text(), content_type="text/plain; charset=utf-8")
    return HttpResponse("# About\n\nContent not available.", content_type="text/plain; charset=utf-8")


urlpatterns = [
    path("admin/", admin.site.urls),

    # ── Auth ──────────────────────────────────────────────────────────────────
    path("api/auth/register/", RegisterView.as_view(), name="auth-register"),
    path("api/auth/turnstile/", TurnstileConfigView.as_view(), name="auth-turnstile"),
    path("api/auth/login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),

    # ── Catalog ───────────────────────────────────────────────────────────────
    path("api/chapters/", ChapterListView.as_view(), name="chapter-list"),
    path("api/chapters/<int:pk>/", ChapterDetailView.as_view(), name="chapter-detail"),

    # ── Books ─────────────────────────────────────────────────────────────────
    path("api/books/", BookListCreateView.as_view(), name="book-list"),
    path("api/books/<int:pk>/", BookDetailView.as_view(), name="book-detail"),

    # Parts
    path("api/books/<int:book_pk>/parts/", PartListCreateView.as_view(), name="part-list"),
    path("api/books/<int:book_pk>/parts/<int:part_pk>/", PartDetailView.as_view(), name="part-detail"),

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

    # ── Signed PDF download (from email links, no auth required) ────────────
    path("api/dl/<str:token>/", DownloadPDFByTokenView.as_view(), name="download-pdf-token"),

    # ── About (serves markdown for frontend rendering) ────────────────────────
    path("api/about/", about_md, name="about"),
]
