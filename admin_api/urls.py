from django.urls import path

from .views import (
    AdminBuildCancelView,
    AdminBuildDetailView,
    AdminBuildDownloadView,
    AdminBuildListView,
    AdminBuildRetryView,
    AdminChapterDetailView,
    AdminChapterListView,
    AdminChapterSyncView,
    AdminUserBooksView,
    AdminUserDetailView,
    AdminUserListView,
    DashboardView,
    WorkersView,
)

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="admin-dashboard"),
    path("workers/", WorkersView.as_view(), name="admin-workers"),

    # Users
    path("users/", AdminUserListView.as_view(), name="admin-user-list"),
    path("users/<int:pk>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("users/<int:pk>/books/", AdminUserBooksView.as_view(), name="admin-user-books"),

    # Chapters
    path("chapters/", AdminChapterListView.as_view(), name="admin-chapter-list"),
    path("chapters/<int:pk>/", AdminChapterDetailView.as_view(), name="admin-chapter-detail"),
    path("chapters/sync/", AdminChapterSyncView.as_view(), name="admin-chapter-sync"),

    # Builds
    path("builds/", AdminBuildListView.as_view(), name="admin-build-list"),
    path("builds/<int:pk>/", AdminBuildDetailView.as_view(), name="admin-build-detail"),
    path("builds/<int:pk>/cancel/", AdminBuildCancelView.as_view(), name="admin-build-cancel"),
    path("builds/<int:pk>/retry/", AdminBuildRetryView.as_view(), name="admin-build-retry"),
    path("builds/<int:pk>/download/", AdminBuildDownloadView.as_view(), name="admin-build-download"),
]
