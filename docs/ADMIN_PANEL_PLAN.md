# OpenChapters Admin Panel — Implementation Plan

## Overview

A web-based administration panel for users with admin privileges to manage the OpenChapters platform. The panel provides a unified interface for user management, chapter catalog oversight, build monitoring, system health, and analytics — replacing the need to use Django's built-in admin or SSH into the server for routine operations.

The admin panel is accessed at `/admin-panel/` (distinct from Django's `/admin/`) and requires the user to have `is_staff=True`.

---

## Design Principles

- **No separate frontend app** — the admin panel is part of the existing React SPA, behind a staff-only route guard
- **Read-heavy, write-light** — most actions are viewing status; destructive actions require confirmation
- **Real-time where it matters** — build queue and worker status poll automatically; everything else loads on demand
- **Audit trail** — all admin actions (user changes, chapter publish/unpublish, build cancellations) are logged

---

## Phase A — Admin Authentication & Layout

**Goal**: Staff-only route guard, admin navigation, and layout shell.

### Tasks

1. Add `is_staff` to the JWT token claims (custom `TokenObtainPairSerializer` that includes `is_staff` in the response)
2. Store `is_staff` in the `AuthContext` so the frontend knows the user's role
3. Create an `AdminRoute` component (like `ProtectedRoute` but also checks `is_staff`)
4. Create the admin layout: sidebar navigation + content area
5. Add an "Admin" link in the main `Navbar` (visible only to staff users)
6. Wire up `/admin-panel/*` routes

### Admin Sidebar Navigation

```
Dashboard
Users
Chapters
Books & Builds
System
Settings
Audit Log
```

### API Changes

```
GET  /api/auth/me/              return current user profile including is_staff
```

### Deliverable

Staff users see an "Admin" link in the nav bar; clicking it opens the admin panel with a sidebar and empty dashboard.

---

## Phase B — Dashboard

**Goal**: At-a-glance overview of platform health and activity.

### Dashboard Cards

| Card | Data | Source |
|---|---|---|
| Total Users | count + new this week | `User.objects.count()` |
| Total Books | count by status (draft/queued/building/complete/failed) | `Book.objects.values('status').annotate(...)` |
| Chapters | published / unpublished count | `Chapter.objects.filter(published=True).count()` |
| Builds Today | count + success/fail ratio | `BuildJob.objects.filter(started_at__date=today)` |
| Queue Depth | pending Celery tasks | Celery inspect API |
| Worker Status | online/offline workers | Celery inspect API |
| Disk Usage | PDF storage size | `os.scandir(BUILD_OUTPUT_DIR)` |
| Recent Activity | last 10 builds with status | `BuildJob.objects.order_by('-started_at')[:10]` |

### API Endpoints

```
GET  /api/admin/dashboard/       aggregated stats (staff only)
GET  /api/admin/workers/         Celery worker status (staff only)
```

### Deliverable

A dashboard page showing key metrics, build activity chart, and worker health.

---

## Phase C — User Management

**Goal**: View, search, edit, and deactivate user accounts.

### Views

| View | Description |
|---|---|
| User List | Paginated table with search/filter: email, date joined, book count, last login, is_active, is_staff |
| User Detail | Profile info, list of user's books, build history, option to edit role or deactivate |

### Actions

| Action | Description | Confirmation |
|---|---|---|
| Toggle `is_active` | Deactivate/reactivate a user (soft delete) | Yes |
| Toggle `is_staff` | Grant/revoke admin access | Yes |
| Reset password | Send password reset email | Yes |
| Delete user | Permanently remove user + books + builds | Double confirmation |
| Impersonate | Log in as user to debug issues (optional, Phase C+) | Yes + audit log |

### API Endpoints

```
GET    /api/admin/users/                 paginated list with search
GET    /api/admin/users/<id>/            user detail with books
PATCH  /api/admin/users/<id>/            update is_active, is_staff
DELETE /api/admin/users/<id>/            delete user
POST   /api/admin/users/<id>/reset-password/   trigger password reset email
```

### Deliverable

Staff can search users, view their activity, and manage accounts without touching the database.

---

## Phase D — Chapter Management

**Goal**: Full control over the chapter catalog from the admin panel.

### Views

| View | Description |
|---|---|
| Chapter List | Table: title, type, chabbr, published, depends_on, last synced |
| Chapter Detail | Full metadata, edit fields, preview TOC, view/upload cover image |
| Sync Status | Last sync time, errors, option to trigger manual sync |

### Actions

| Action | Description |
|---|---|
| Toggle `published` | Show/hide a chapter from the public catalog |
| Edit metadata | Override title, description, keywords, chapter_type, depends_on |
| Trigger sync | Run `sync_chapters` on demand, show live progress |
| Upload cover image | Replace the auto-generated cover with a custom image |
| Reorder chapters | Change the default display order in the browser |

### API Endpoints

```
GET    /api/admin/chapters/              paginated list (all, including unpublished)
GET    /api/admin/chapters/<id>/         chapter detail (editable fields)
PATCH  /api/admin/chapters/<id>/         update metadata
POST   /api/admin/chapters/sync/         trigger sync_chapters task
GET    /api/admin/chapters/sync/status/  poll sync progress
POST   /api/admin/chapters/<id>/cover/   upload cover image
```

### Deliverable

Staff can manage the chapter catalog, publish/unpublish chapters, edit metadata, and trigger syncs.

---

## Phase E — Build Management

**Goal**: Monitor, inspect, and manage book builds.

### Views

| View | Description |
|---|---|
| Build Queue | Active and queued builds with real-time status |
| Build History | Paginated table: book title, user, status, started, duration, PDF size |
| Build Detail | Full log output, error details, PDF download link, retry button |

### Actions

| Action | Description | Confirmation |
|---|---|---|
| View build log | Full arara/LaTeX output | No |
| Download PDF | Download any user's completed PDF | No |
| Cancel build | Revoke a queued/running Celery task | Yes |
| Retry build | Re-enqueue a failed build | Yes |
| Purge old PDFs | Delete PDFs older than N days | Yes |

### API Endpoints

```
GET    /api/admin/builds/                paginated list with filters (status, user, date range)
GET    /api/admin/builds/<id>/           build detail with full log
POST   /api/admin/builds/<id>/cancel/    revoke Celery task
POST   /api/admin/builds/<id>/retry/     re-enqueue build
GET    /api/admin/builds/<id>/download/  download PDF (any user's)
POST   /api/admin/builds/purge/          delete old PDFs
GET    /api/admin/builds/stats/          build statistics (counts by day/week, avg duration, failure rate)
```

### Deliverable

Staff can monitor all builds, inspect failures, retry, and manage PDF storage.

---

## Phase F — System Monitoring

**Goal**: Real-time visibility into infrastructure health.

### Views

| View | Description |
|---|---|
| Workers | Celery worker list with status, active tasks, uptime |
| Queue | Task queue depth, oldest pending task |
| Storage | PDF directory size, count, oldest/newest files |
| Services | Health check status for PostgreSQL, RabbitMQ, Celery |

### Health Checks

| Service | Check |
|---|---|
| PostgreSQL | `SELECT 1` query |
| RabbitMQ | Celery `inspect.ping()` |
| Celery workers | `inspect.active()` |
| Disk space | `shutil.disk_usage()` |
| GitHub API | Token validity + rate limit remaining |

### API Endpoints

```
GET  /api/admin/system/health/       service health checks
GET  /api/admin/system/workers/      Celery worker details
GET  /api/admin/system/storage/      PDF storage stats
GET  /api/admin/system/github/       GitHub token status + rate limit
```

### Deliverable

Staff can see at a glance whether all services are healthy and identify bottlenecks.

---

## Phase G — Site Settings

**Goal**: Configure platform behavior without redeploying.

### Approach

Create a `SiteSetting` model that stores key-value pairs. Settings can be overridden from the admin panel. Environment variables remain the source of truth for secrets; the admin panel manages non-sensitive operational settings.

### Configurable Settings

| Setting | Type | Description |
|---|---|---|
| `site_name` | string | Displayed in the navbar and emails |
| `welcome_message` | text | Shown on the chapter browser page |
| `max_chapters_per_book` | integer | Limit chapters in a single book |
| `max_concurrent_builds` | integer | Celery concurrency limit |
| `pdf_retention_days` | integer | Auto-purge PDFs older than this |
| `registration_enabled` | boolean | Open/close registration |
| `build_enabled` | boolean | Enable/disable the build pipeline (maintenance mode) |
| `announcement_banner` | text | Shown at top of all pages (e.g., maintenance notice) |

### Data Model

```python
class SiteSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
```

### API Endpoints

```
GET    /api/admin/settings/              list all settings
PATCH  /api/admin/settings/              update one or more settings
GET    /api/settings/public/             non-auth: returns public settings (site_name, announcement, registration_enabled)
```

### Deliverable

Staff can toggle registration, set build limits, display announcements, and adjust retention policies.

---

## Phase H — Audit Log

**Goal**: Immutable record of all admin actions for accountability.

### Data Model

```python
class AuditEntry(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)  # e.g., "user.deactivate", "chapter.unpublish"
    target_type = models.CharField(max_length=50)  # e.g., "User", "Chapter", "Build"
    target_id = models.IntegerField()
    detail = models.JSONField(default=dict)  # before/after values
    ip_address = models.GenericIPAddressField(null=True)
```

### Views

| View | Description |
|---|---|
| Audit Log | Paginated, filterable list: who did what, when, to which object |

### API Endpoints

```
GET  /api/admin/audit/                   paginated log with filters (user, action, date range, target)
```

### Automatic Logging

Every admin API endpoint that modifies data calls `AuditEntry.log(request, action, target, detail)` before returning. This is implemented as a mixin or decorator on admin views.

### Deliverable

Complete audit trail of all admin actions, searchable and filterable.

---

## Phase I — Analytics (Optional)

**Goal**: Usage insights to guide platform development.

### Metrics

| Metric | Visualization |
|---|---|
| Builds per day/week/month | Line chart |
| Most popular chapters | Bar chart (times included in books) |
| Build success/failure rate | Pie chart |
| Average build duration | Line chart over time |
| User registrations over time | Line chart |
| Chapter dependency graph | Network diagram |
| Active users (built a book in last 30 days) | Count |

### API Endpoints

```
GET  /api/admin/analytics/builds/        build stats over time
GET  /api/admin/analytics/chapters/      chapter popularity
GET  /api/admin/analytics/users/         registration and activity trends
```

### Deliverable

Visual analytics dashboard showing platform usage trends.

---

## Implementation Sequence

```
Phase A  Admin auth & layout              ~2 days
Phase B  Dashboard                        ~3 days
Phase C  User management                  ~3 days
Phase D  Chapter management               ~3 days
Phase E  Build management                 ~3 days
Phase F  System monitoring                ~2 days
Phase G  Site settings                    ~2 days
Phase H  Audit log                        ~2 days
Phase I  Analytics (optional)             ~3 days
```

**Total: ~3 weeks** (Phases A–H); Phase I is optional and can be added later.

### Recommended Priority

1. **Phases A + B** first — gives immediate visibility into platform health
2. **Phases C + D** next — the most frequent admin tasks
3. **Phase E** — essential for debugging build issues
4. **Phases F + G + H** — operational maturity
5. **Phase I** — when the platform has enough usage data to make analytics meaningful

---

## Technical Notes

### Permission Model

All admin API endpoints use a custom permission class:

```python
class IsStaffUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff
```

### Frontend Structure

```
frontend/src/
  admin/
    AdminLayout.tsx          Sidebar + content shell
    AdminRoute.tsx           Staff-only route guard
    pages/
      DashboardPage.tsx
      UsersPage.tsx
      UserDetailPage.tsx
      ChaptersPage.tsx
      ChapterDetailPage.tsx
      BuildsPage.tsx
      BuildDetailPage.tsx
      SystemPage.tsx
      SettingsPage.tsx
      AuditLogPage.tsx
      AnalyticsPage.tsx
    components/
      StatCard.tsx
      DataTable.tsx           Reusable sortable/filterable table
      ConfirmDialog.tsx       Confirmation modal for destructive actions
      StatusBadge.tsx
      BuildLogViewer.tsx
    api/
      admin.ts               All admin API calls
```

### Key Dependencies

| Package | Purpose |
|---|---|
| `recharts` or `chart.js` | Dashboard and analytics charts |
| `@tanstack/react-table` | Sortable, filterable data tables |
| Existing stack | No new backend dependencies needed |

---

## Security Considerations

- All admin endpoints require `is_staff=True`
- Destructive actions (delete user, purge PDFs) require double confirmation
- Audit log entries cannot be modified or deleted via the API
- Rate limiting applies to admin endpoints (higher limits than regular users)
- Admin actions on other staff users require `is_superuser=True`
- Impersonation (if implemented) generates a prominent audit log entry
