# OpenChapters Admin Guide

This guide covers the administration panel for managing the OpenChapters platform. The admin panel is accessible to users with staff privileges at `/admin-panel/`.

---

## Table of Contents

1. [Accessing the Admin Panel](#accessing-the-admin-panel)
2. [Dashboard](#dashboard)
3. [User Management](#user-management)
4. [Chapter Management](#chapter-management)
5. [Build Management](#build-management)
6. [System Monitoring](#system-monitoring)
7. [Site Settings](#site-settings)
8. [Audit Log](#audit-log)
9. [Analytics](#analytics)
10. [Granting Admin Access](#granting-admin-access)

---

## Accessing the Admin Panel

The admin panel is available to any user with `is_staff=True`. When logged in as a staff user, an **Admin** button appears in the top-right corner of the navigation bar.

Click **Admin** to enter the admin panel. The panel has its own sidebar navigation and does not use the regular site layout. Click **Back to site** in the sidebar to return to the main site.

## Dashboard

**Path:** `/admin-panel/`

The dashboard provides an at-a-glance overview of platform health and activity. It auto-refreshes every 15 seconds.

### Stat Cards

| Card | Description |
|---|---|
| **Users** | Total registered users and new registrations this week |
| **Chapters** | Published and unpublished chapter counts |
| **Books** | Total books and number completed |
| **Builds today** | Today's builds with success/failure breakdown |

### Book Status Breakdown

Shows the count of books in each status: Draft, Queued, Building, Failed.

### Infrastructure

| Card | Description |
|---|---|
| **PDFs stored** | Number of generated PDFs and total storage size |
| **Workers online** | Number of active Celery workers |
| **Active tasks** | Currently running build tasks |

### Workers

Each online Celery worker is shown with its name, pool type, concurrency setting, and number of active tasks.

### Recent Builds

A table of the 10 most recent builds showing book title, user, status, start time, and duration.

## User Management

**Path:** `/admin-panel/users`

### User List

A searchable, paginated table of all registered users.

| Column | Description |
|---|---|
| **Email** | Click to view user detail |
| **Joined** | Registration date |
| **Books** | Number of books created |
| **Last login** | Most recent login date |
| **Role** | Badge: user, staff, or superuser |
| **Status** | Badge: active or inactive |
| **Delete** | Delete the user (with double confirmation) |

Use the search box to filter by email address.

### Creating a User

Click **+ Add User** to open the creation form:

1. Enter the user's email address
2. Set a password (minimum 8 characters)
3. Optionally check **Staff** to grant admin access
4. Click **Create**

The user can immediately log in with the provided credentials.

### User Detail

**Path:** `/admin-panel/users/:id`

Shows the user's profile information and a list of their books.

**Available actions:**

| Action | Description |
|---|---|
| **Activate / Deactivate** | Soft-disable the account (prevents login without deleting data) |
| **Grant staff / Revoke staff** | Toggle admin panel access |
| **Delete user** | Permanently delete the user and all their books (requires double confirmation) |

**Safeguards:**
- You cannot delete your own account from the admin panel
- All actions are recorded in the audit log

## Chapter Management

**Path:** `/admin-panel/chapters`

### Chapter List

A searchable table of all chapters, including unpublished ones.

| Column | Description |
|---|---|
| **Title** | Click to view chapter detail |
| **Abbr** | The `\chabbr` LaTeX abbreviation |
| **Type** | Badge: foundational or topical |
| **Published** | Whether the chapter appears in the public catalog |
| **Dependencies** | Foundational chapters this chapter references |
| **Last synced** | When the chapter was last updated from GitHub |

### Syncing from GitHub

Click **Sync from GitHub** to trigger an immediate catalog sync. The sync:

1. Reads `chapter.json` from each subdirectory in the OpenChapters monorepo
2. Creates or updates chapter records in the database
3. Shows live output with the number of chapters created, updated, or skipped

The catalog also syncs automatically every night at 03:00 UTC.

### Chapter Detail

**Path:** `/admin-panel/chapters/:id`

Shows full chapter metadata with two panels:

- **Table of Contents** — section headings from the chapter
- **Details** — authors, dependencies, entry file, GitHub path, last sync time

**Available actions:**

| Action | Description |
|---|---|
| **Publish / Unpublish** | Toggle whether the chapter appears in the public catalog. Unpublished chapters cannot be added to books. |
| **Edit metadata** | Opens an inline form to change title, description, type (foundational/topical), and keywords. Changes are stored in the database and override synced values. |

## Build Management

**Path:** `/admin-panel/builds`

### Build List

A filterable, paginated table of all builds across all users. Auto-refreshes every 10 seconds.

**Filters:**
- **Status dropdown** — filter by draft, queued, building, complete, or failed
- **Search** — filter by book title or user email

| Column | Description |
|---|---|
| **Book** | Book title |
| **User** | Owner's email |
| **Status** | Color-coded badge with error indicator |
| **Started** | Build start timestamp |
| **Duration** | Time from start to finish |
| **PDF** | File size of the generated PDF |
| **Details** | Link to the build detail page |

### Build Detail

**Path:** `/admin-panel/builds/:id`

Shows complete build information including metadata, actions, and the full build log.

**Metadata:** start/finish times, duration, Celery task ID.

**Available actions:**

| Action | When available | Description |
|---|---|---|
| **Cancel build** | Queued or Building | Revokes the Celery task and marks the build as failed |
| **Retry build** | Failed or Complete | Re-enqueues the build for a fresh attempt |
| **Download PDF** | Complete | Downloads the generated PDF (works for any user's book) |

**Error panel:** If the build failed, the error message is shown in a red panel.

**Build log:** The full build output (git clone, arara, LaTeX) is displayed in a dark terminal-style viewer. This includes:

- Workspace creation and template file copying
- Git clone output
- Script execution (concat_bibs, collect_images, build_main_tex, generate_gin)
- arara output with step-by-step results
- LaTeX error messages (extracted from `main.log` on failure)

## System Monitoring

**Path:** `/admin-panel/system`

### Overall Status

A banner at the top shows the overall system health:
- **Green** — all systems healthy
- **Yellow** — some warnings (e.g., disk usage > 90%)
- **Red** — critical issues detected

### Service Health Cards

Each service is checked and displayed as a card. Auto-refreshes every 15 seconds.

| Service | What is checked | Warning threshold |
|---|---|---|
| **PostgreSQL** | `SELECT 1` query | Connection failure |
| **RabbitMQ** | Celery worker ping | No workers respond |
| **Celery** | Worker count, active tasks, queued tasks | Zero workers |
| **Disk** | Free space, total space, usage percentage | > 90% used |
| **PDF storage** | File count, total size, oldest/newest file dates | — |

### GitHub API

Shows the status of the configured GitHub token:

| Field | Description |
|---|---|
| **Status** | Valid, invalid, expired, or not configured |
| **Rate limit** | Remaining API calls out of the hourly limit |
| **Resets at** | When the rate limit counter resets |

## Site Settings

**Path:** `/admin-panel/settings`

Runtime configuration that can be changed without redeploying. Settings are stored in the database and take effect immediately.

### Available Settings

| Setting | Type | Default | Description |
|---|---|---|---|
| **Site name** | Text | OpenChapters | Displayed in the navbar and emails |
| **Welcome message** | Text | (empty) | Shown on the chapter browser page |
| **Announcement banner** | Text | (empty) | Shown at the top of all pages (e.g., maintenance notice) |
| **Registration enabled** | Toggle | On | When off, the registration page is disabled |
| **Build pipeline enabled** | Toggle | On | When off, no new builds can be started |
| **Max chapters per book** | Number | 30 | Maximum chapters allowed in a single book |
| **Max concurrent builds** | Number | 4 | Celery concurrency limit for builds |
| **PDF retention (days)** | Number | 90 | How long generated PDFs are kept before cleanup |

Click **Save settings** to apply changes. All settings changes are recorded in the audit log.

### Public Settings Endpoint

The frontend reads public settings (site name, announcement banner, registration status) from `GET /api/settings/public/` without authentication. This allows the announcement banner and registration toggle to work without requiring a page reload.

## Audit Log

**Path:** `/admin-panel/audit`

An immutable, searchable record of all administrative actions. Entries cannot be edited or deleted.

### Filters

- **Action** — text filter (e.g., "user", "delete", "settings")
- **Target type** — dropdown: User, Chapter, BuildJob, SiteSetting
- **User email** — text filter for the admin who performed the action

### Table Columns

| Column | Description |
|---|---|
| **Time** | When the action occurred |
| **User** | Email of the admin who performed it |
| **Action** | Color-coded badge: `user.create` (green), `chapter.update` (blue), `user.delete` (red), `build.cancel` (yellow), `build.retry` (purple) |
| **Target** | Object type and ID (e.g., User #3) |
| **Details** | JSON showing what changed (before/after values for updates, email for deletions, etc.) |
| **IP** | IP address of the admin |

### Logged Actions

| Action | Trigger |
|---|---|
| `user.create` | Admin creates a new user |
| `user.update` | Admin toggles is_active or is_staff |
| `user.delete` | Admin deletes a user |
| `chapter.update` | Admin edits chapter metadata or toggles published |
| `build.cancel` | Admin cancels a queued/running build |
| `build.retry` | Admin re-queues a failed/completed build |
| `settings.update` | Admin changes site settings |

## Analytics

**Path:** `/admin-panel/analytics`

Visual charts showing platform usage trends.

### Builds per Day

A stacked bar chart showing the last 30 days of builds:
- **Green bars** — successful builds
- **Red bars** — failed builds

Hover over a bar to see the exact counts for that day.

### Most Included Chapters

A horizontal bar chart showing the most popular chapters by how many times they have been included in user books. Useful for understanding which content is most in demand.

### User Registrations

A line chart showing daily user registrations over the last 90 days. Useful for tracking growth and the impact of announcements or outreach.

## Granting Admin Access

### First Admin (Setup)

During initial deployment, create the first admin user via the command line:

```bash
docker compose exec web python manage.py createsuperuser
```

This creates a user with both `is_staff=True` and `is_superuser=True`.

### Additional Admins

Once you have admin access, you can grant staff privileges to other users:

1. Go to **Users** in the admin panel
2. Click the user's email to open their detail page
3. Click **Grant staff**

Or create a new staff user directly with the **+ Add User** button and check the **Staff** checkbox.

### Removing Admin Access

1. Go to the user's detail page
2. Click **Revoke staff**

The user will immediately lose access to the admin panel (on their next page load or API call).
