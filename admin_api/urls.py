from django.urls import path

from .views import (
    AdminAnalyticsBuildsView,
    AdminAnalyticsChaptersView,
    AdminAnalyticsUsersView,
    AdminAuditLogView,
    AdminBuildCancelView,
    AdminBuildDetailView,
    AdminBuildDownloadView,
    AdminBuildListView,
    AdminBuildRetryView,
    AdminChapterDetailView,
    AdminChapterListView,
    AdminChapterSyncView,
    AdminChapterUpdateTOCView,
    AdminChapterBuildHtmlView,
    AdminChapterUpdateThumbnailsView,
    AdminDisciplineDetailView,
    AdminDisciplineListView,
    AdminSettingsView,
    AdminUserBooksView,
    AdminUserDetailView,
    AdminUserListView,
    DashboardView,
    SystemGitHubView,
    SystemHealthView,
    WorkersView,
)

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="admin-dashboard"),
    path("workers/", WorkersView.as_view(), name="admin-workers"),

    # Users
    path("users/", AdminUserListView.as_view(), name="admin-user-list"),
    path("users/<int:pk>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("users/<int:pk>/books/", AdminUserBooksView.as_view(), name="admin-user-books"),

    # Disciplines
    path("disciplines/", AdminDisciplineListView.as_view(), name="admin-discipline-list"),
    path("disciplines/<int:pk>/", AdminDisciplineDetailView.as_view(), name="admin-discipline-detail"),

    # Chapters
    path("chapters/", AdminChapterListView.as_view(), name="admin-chapter-list"),
    path("chapters/<int:pk>/", AdminChapterDetailView.as_view(), name="admin-chapter-detail"),
    path("chapters/sync/", AdminChapterSyncView.as_view(), name="admin-chapter-sync"),
    path("chapters/update-toc/", AdminChapterUpdateTOCView.as_view(), name="admin-chapter-toc"),
    path("chapters/update-thumbnails/", AdminChapterUpdateThumbnailsView.as_view(), name="admin-chapter-thumbnails"),
    path("chapters/build-html/", AdminChapterBuildHtmlView.as_view(), name="admin-chapter-build-html"),

    # Builds
    path("builds/", AdminBuildListView.as_view(), name="admin-build-list"),
    path("builds/<int:pk>/", AdminBuildDetailView.as_view(), name="admin-build-detail"),
    path("builds/<int:pk>/cancel/", AdminBuildCancelView.as_view(), name="admin-build-cancel"),
    path("builds/<int:pk>/retry/", AdminBuildRetryView.as_view(), name="admin-build-retry"),
    path("builds/<int:pk>/download/", AdminBuildDownloadView.as_view(), name="admin-build-download"),

    # System
    path("system/health/", SystemHealthView.as_view(), name="admin-system-health"),
    path("system/github/", SystemGitHubView.as_view(), name="admin-system-github"),

    # Settings
    path("settings/", AdminSettingsView.as_view(), name="admin-settings"),

    # Audit log
    path("audit/", AdminAuditLogView.as_view(), name="admin-audit-log"),

    # Analytics
    path("analytics/builds/", AdminAnalyticsBuildsView.as_view(), name="admin-analytics-builds"),
    path("analytics/chapters/", AdminAnalyticsChaptersView.as_view(), name="admin-analytics-chapters"),
    path("analytics/users/", AdminAnalyticsUsersView.as_view(), name="admin-analytics-users"),
]
