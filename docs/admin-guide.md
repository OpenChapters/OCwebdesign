# OpenChapters Admin Guide

This guide covers the administration panel for managing the OpenChapters platform. The admin panel is accessible to users with staff privileges at `/admin-panel/`.

---

## Table of Contents

1. [Accessing the Admin Panel](#accessing-the-admin-panel)
2. [Dashboard](#dashboard)
3. [User Management](#user-management)
4. [Chapter Management](#chapter-management)
5. [Worked Examples](#worked-examples)
6. [Build Management](#build-management)
7. [System Monitoring](#system-monitoring)
8. [Site Settings](#site-settings)
9. [Audit Log](#audit-log)
10. [Analytics](#analytics)
11. [Granting Admin Access](#granting-admin-access)

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
| **Examples** | Number of published [worked examples](#worked-examples) tagged to the chapter; click to jump to those examples |
| **Last synced** | When the chapter was last updated from GitHub |

### Syncing from GitHub

Click **Sync from GitHub** to trigger an immediate catalog sync. The sync:

1. Reads `chapter.json` from each subdirectory in the OpenChapters monorepo
2. Creates or updates chapter records in the database
3. Shows live output with the number of chapters created, updated, or skipped

The catalog also syncs automatically every night at 03:00 UTC.

### Updating Thumbnails

Click **Update Thumbnails** to regenerate cover images for chapters whose header image has changed on GitHub. The admin endpoint downloads the latest header PDFs, crops them to cover-image proportions, and updates the local cache. Any chapters whose covers are already up to date are skipped.

### Updating Table of Contents

Click **Update TOC** to re-extract section headings from each chapter's `.tex` source on GitHub and update the TOC stored in the database. This is useful after an author has added or renamed sections.

### Building Chapter HTML

Two buttons control HTML builds:

- **Build Stale HTML** — queues HTML builds only for chapters whose source has changed since their last HTML build (or never had one). Recommended for routine updates.
- **Rebuild All HTML** — queues HTML builds for every published chapter, regardless of whether the source has changed. Use this after upgrading the LaTeX template or changing the build pipeline.

Both buttons dispatch individual Celery tasks to the worker queue. Celery's worker concurrency setting controls how many chapters build in parallel. Each chapter typically takes 30 seconds to a few minutes; large chapters may take longer.

Progress is visible in the worker logs:

```bash
docker compose -f docker-compose.prod.yml logs worker-builds worker-default --tail 50
```

If `HTML_BUILD_ENABLED=True` is set in `.env.prod`, the nightly sync also dispatches stale HTML rebuilds automatically.

After each successful HTML build, the chapter's search index is refreshed so the new content is immediately searchable.

**About cross-chapter references.** Per-chapter HTML builds only see their own chapter's source. Any `\ref{...}` pointing to a label in a different chapter (e.g., a chapter listed in `depends_on`) cannot be resolved. In PDF these render as bold `??`; in the HTML reader they render as the label name in italics (e.g., *NUMSYS:sec:quaternions*), which gives readers a hint about the target. Cross-chapter linking will become possible in per-book HTML builds (planned feature).

### Building Foundational Labels-PDFs

For each foundational chapter, the platform builds a separate PDF that has every `\label{...}` printed next to its anchor (via the `showkeys` package, dropped to `\tiny` so long keys stay on the page). Prospective authors download this from the chapter detail page to discover the exact label keys they should target with `\ref{...}` in their own chapters.

There is no admin button for this build (the artifact is not surfaced in the admin Chapters list). Instead, the build is triggered automatically:

- **Nightly**, when `HTML_BUILD_ENABLED=True` is set in `.env.prod`. The `sync_chapters` task fans out a `build_chapter_pdf_labels` task for every published foundational chapter after dispatching the stale-HTML rebuilds.
- **Manually**, by running the management command on the worker:
  ```bash
  docker compose -f docker-compose.prod.yml exec worker-builds python manage.py build_chapter_pdf_labels
  # or for a single chapter:
  docker compose -f docker-compose.prod.yml exec worker-builds python manage.py build_chapter_pdf_labels --chabbr NUMSYS
  ```

The artifacts land under `media/pdf_labels/<chabbr>.pdf` (a shared named volume mounted on both `web` and `worker`). The `Download PDF (with labels)` button only appears on a foundational chapter's detail page when the artifact exists on disk — the chapter serializer reports `has_pdf_labels` based on a filesystem check.

### Chapter Detail

**Path:** `/admin-panel/chapters/:id`

Shows full chapter metadata with two panels:

- **Table of Contents** — section headings from the chapter
- **Details** — authors, dependencies, entry file, GitHub path, last sync time

**Available actions:**

| Action | Description |
|---|---|
| **Publish / Unpublish** | Toggle whether the chapter appears in the public catalog. Unpublished chapters cannot be added to books. |
| **Edit metadata** | Opens an inline form to change title, description, type (foundational/topical), keywords, and review information (reviewer name + review date). Changes are stored in the database and override synced values. |

Chapters with a successfully built HTML version show the build timestamp in the details panel. Users can read these chapters online via the **Read Online** button on the public chapter page and search within them via the global Search page.

## Worked Examples

**Path:** `/admin-panel/examples`

Authors submit short LaTeX problems with full solutions, each tagged to one or more chapters. Submitted examples wait in a review queue; an admin approves them to publish, or rejects with a reason that the author can read in the editor and address.

### Review Queue

The page is organised by status tabs:

- **Pending** — examples awaiting review (the default tab).
- **Published** — already approved.
- **Rejected** — bounced back to the author with a reason; the entry returns to **Draft** as soon as the author edits, and can be re-submitted.
- **Drafts** — saved but not yet submitted (rare to see here; mostly useful for diagnostic purposes).

Each row shows:

- The example id, the author's display name, and the submission date.
- The chapter chabbrs the example is tagged to, with the **primary chapter** marked with an asterisk. The primary chapter determines which preamble is used to compile the snippet preview, and (for book builds) which chapter the example renders under when more than one of its tags appears in the same book.
- The difficulty (introductory / standard / advanced).
- A truncated preview of the statement source (raw LaTeX, ~400 characters).
- An **Open detail →** link to the public detail page for that example.
- **Open preview PDF ↗** when the snippet has been compiled. The link is signed and embedded in the URL, so it opens directly in a new tab without auth.
- A small **build failed** indicator if the most recent compile produced an error log instead of a PDF (use the `Open detail` link to read the log).

### Approve / Reject

For each pending example, the row carries two action buttons:

- **Approve** — moves the example to **Published**. It immediately appears on `/examples`, on each tagged chapter's detail page, and is eligible for inclusion in book builds (subject to the per-build flag in the [user-facing build flow](user-guide.md#building-your-book)).
- **Reject…** — opens an inline reason input. Type a short message (e.g., "Please show intermediate steps for the determinant expansion") and click **Confirm**. The reason is shown to the author at the top of the editor and at the top of the public detail page.

### Build Pipeline

The snippet preview pipeline is parallel to the chapter HTML / labels-PDF pipelines:

- A Celery task `catalog.build_example_preview` runs in the worker container.
- The management command renders `Build/scripts/main_example.tex.j2` with the example's primary-chapter preamble + the inline statement / solution, runs `arara`, and writes `media/examples/<id>.pdf` atomically.
- Successful builds set `preview_built_at` on the Example record; failures capture the last 8 KB of the arara output to `preview_build_log` (visible to author and admin).
- The named volume `media_examples` is shared by the `web` and `worker` containers (declared in `docker-compose.prod.yml`), so the web service can stream the artifact back over `/api/examples/<id>/preview.pdf`.

You can build an example's preview manually:

```bash
docker compose -f docker-compose.prod.yml exec worker-builds python manage.py build_example_preview --id 17
```

If the build fails, the worker preserves the workspace at `/tmp/ocexample-<uuid>/` for inspection — `main.log` has the LaTeX error, `main.tex` shows the rendered template.

### Submission Constraints

The submit endpoint requires a fresh successful preview — the server compares `preview_built_at >= updated_at`, so any edit to the example invalidates the previous preview and the author has to rebuild it before submitting. This guarantees the queue never contains entries that don't compile.

The admin queue link is also disabled for examples with no preview built yet; admins should never see "broken" entries waiting on review.

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

### Git Provider API

Shows the status of the configured git access token (GitHub or GitLab):

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
