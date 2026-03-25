from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from books.views import (
    BookDetailView,
    BookListCreateView,
    BuildStatusView,
    BuildTriggerView,
    LibraryView,
    PartChapterDetailView,
    PartChapterListCreateView,
    PartChapterReorderView,
    PartDetailView,
    PartListCreateView,
)
from catalog.views import ChapterDetailView, ChapterListView
from users.views import RegisterView

urlpatterns = [
    path("admin/", admin.site.urls),

    # ── Auth ──────────────────────────────────────────────────────────────────
    path("api/auth/register/", RegisterView.as_view(), name="auth-register"),
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

    # ── Library ───────────────────────────────────────────────────────────────
    path("api/library/", LibraryView.as_view(), name="library"),
]
