# OpenChapters API Reference

The OpenChapters API is a RESTful JSON API built with Django REST Framework. All endpoints are served under the `/api/` prefix.

> **Live reference.** A live OpenAPI 3 schema is generated from the server by [drf-spectacular](https://drf-spectacular.readthedocs.io/) and exposed under `/api/schema/`. Two interactive doc viewers are also wired up:
>
> - `/api/schema/swagger-ui/` — Swagger UI; try endpoints from the browser after authorizing with a JWT.
> - `/api/schema/redoc/` — ReDoc; cleaner read-only browser, better for reading the contracts.
>
> The schema is the source of truth for the request/response shapes documented below. If a payload here ever disagrees with what `/api/schema/` returns, trust the schema.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Pagination](#pagination)
3. [Error Responses](#error-responses)
4. [Endpoints](#endpoints)
   - [Auth](#auth)
   - [Password Reset](#password-reset)
   - [Profile](#profile)
   - [Disciplines](#disciplines)
   - [Chapters](#chapters)
   - [Books](#books)
   - [Parts](#parts)
   - [Book Chapters](#book-chapters)
   - [Build](#build)
   - [Library](#library)
   - [Community Library](#community-library)
   - [Worked Examples](#worked-examples)
   - [Cover Images](#cover-images)

---

## Authentication

The API uses **JWT (JSON Web Tokens)** for authentication. Most endpoints require a valid access token.

### Obtaining Tokens

```
POST /api/auth/login/
```

**Request body:**
```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Response (200):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

### Using Tokens

Include the access token in the `Authorization` header:

```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

### Token Lifetimes

| Token | Lifetime |
|---|---|
| Access token | 5 hours |
| Refresh token | 7 days |

### Refreshing Tokens

```
POST /api/auth/token/refresh/
```

**Request body:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Response (200):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

## Pagination

List endpoints return paginated results using Django REST Framework's page number pagination.

```json
{
  "count": 17,
  "next": "http://localhost:8000/api/chapters/?page=2",
  "previous": null,
  "results": [...]
}
```

| Parameter | Default | Description |
|---|---|---|
| `page` | 1 | Page number |
| Page size | 50 | Fixed; not configurable per request |

## Error Responses

### 400 Bad Request
```json
{
  "field_name": ["Error message."]
}
```

### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 404 Not Found
```json
{
  "detail": "Not found."
}
```

### 409 Conflict
```json
{
  "detail": "Build already in progress."
}
```

---

## Endpoints

### Auth

#### Register

```
POST /api/auth/register/
```

Create a new user account.

**Request body:**
```json
{
  "email": "user@example.com",
  "full_name": "Jane Smith",
  "password": "minimum8chars"
}
```

**Response (201):**
```json
{
  "detail": "Account created."
}
```

**Errors:**
- `400` — email already in use, password too short, or password too common

#### Login

```
POST /api/auth/login/
```

See [Obtaining Tokens](#obtaining-tokens) above.

#### Refresh Token

```
POST /api/auth/token/refresh/
```

See [Refreshing Tokens](#refreshing-tokens) above.

---

### Password Reset

#### Request Reset Link

```
POST /api/auth/forgot-password/
```

**Request body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "detail": "If that email exists, a reset link has been sent."
}
```

Always returns success regardless of whether the email exists (prevents email enumeration). The reset link is sent via the configured SMTP server in production, or logged to the server console in development.

#### Reset Password

```
POST /api/auth/reset-password/
```

**Request body:**
```json
{
  "uid": "MQ",
  "token": "d61ugv-1ff323a90a10fc...",
  "password": "newpassword123"
}
```

- `uid` and `token` are from the reset link URL: `/reset-password/<uid>/<token>`
- Tokens expire after 3 days (Django's `PASSWORD_RESET_TIMEOUT`)

**Response (200):**
```json
{
  "detail": "Password has been reset. You can now sign in."
}
```

---

### Profile

#### Get Profile

```
GET /api/auth/profile/
```

Returns the current user's account information. Requires authentication.

**Response (200):**
```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "Jane Smith",
  "is_staff": false,
  "date_joined": "2026-03-25T15:50:00Z",
  "last_login": "2026-03-26T10:30:00Z",
  "share_builds": false
}
```

`share_builds` is the user's opt-in to listing completed books in the public [Community Library](#community-library).

#### Update Profile

```
PATCH /api/auth/profile/
```

**Request body** (any subset of editable fields):
```json
{
  "full_name": "Jane A. Smith",
  "share_builds": true
}
```

**Response (200):** Updated profile object.

#### Delete Account

```
DELETE /api/auth/profile/
```

Permanently deletes the authenticated user's account and all associated data.

**Response:** `204 No Content`

#### Change Password

```
POST /api/auth/change-password/
```

**Request body:**
```json
{
  "current_password": "oldpassword",
  "new_password": "newpassword123"
}
```

**Response (200):**
```json
{
  "detail": "Password changed."
}
```

---

### Disciplines

#### List Disciplines

```
GET /api/disciplines/
```

Returns all published disciplines. No authentication required. No pagination.

**Response (200):**
```json
[
  {
    "id": 1,
    "name": "Materials Science and Engineering",
    "slug": "mse",
    "color_primary": "#2563eb"
  }
]
```

---

### Chapters

#### List Chapters

```
GET /api/chapters/
```

Returns all published chapters. No authentication required.

**Query parameters:**
- `page` — page number (default: 1)
- `discipline` — filter by discipline slug (e.g., `?discipline=mse`). Omit to list all disciplines.

**Response (200):**
```json
{
  "count": 16,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 5,
      "title": "Concepts of Linear Algebra",
      "authors": ["Marc De Graef"],
      "description": "",
      "toc": [
        "Matrices and Linear Equations",
        "General properties of matrices",
        "The Determinant of a matrix",
        "The Inverse of a matrix",
        "Solving Systems of Equations by Gaussian Elimination",
        "Eigenvalues and Eigenvectors"
      ],
      "cover_image_url": "https://raw.githubusercontent.com/OpenChapters/OpenChapters/master/src/LinearAlgebra/cover.png",
      "keywords": [],
      "chapter_type": "foundational",
      "chabbr": "LINALG",
      "depends_on": [],
      "related_to": [],
      "version": "1.0",
      "concept_doi": "10.5072/openchapters.linalg.concept",
      "current_version_doi": "10.5072/openchapters.linalg.1-0",
      "doi_versions": [
        {
          "version": "1.0",
          "doi": "10.5072/openchapters.linalg.1-0",
          "commit_sha": "a1b2c3d",
          "is_current": true,
          "registered_at": "2026-03-25T15:49:09.621132Z"
        }
      ],
      "github_repo": "OpenChapters/OpenChapters",
      "chapter_subdir": "src/LinearAlgebra",
      "cached_at": "2026-03-25T15:49:09.621132Z"
    }
  ]
}
```

**Chapter fields:**

| Field | Type | Description |
|---|---|---|
| `id` | integer | Unique identifier |
| `title` | string | Chapter title |
| `authors` | string[] | List of author names |
| `description` | string | Chapter description (may be empty) |
| `toc` | string[] | Section headings (table of contents) |
| `cover_image_url` | string | URL to cover image on GitHub |
| `keywords` | string[] | Search keywords |
| `chapter_type` | string | `"foundational"` or `"topical"` |
| `chabbr` | string | Unique LaTeX abbreviation (e.g. `"LINALG"`) |
| `depends_on` | string[] | `chabbr` values of **foundational** prerequisites (hard). Auto-included in builds, transitively, in a prepended "Foundations" part |
| `related_to` | string[] | `chabbr` values of **topical** chapters cross-referenced (soft). Offered as optional suggestions in the Book Editor; never auto-included in builds |
| `version` | string | Author-declared version string from `chapter.json` (may be empty if unversioned) |
| `concept_doi` | string | Persistent DOI for the chapter; always resolves to the latest version (empty until first registration) |
| `current_version_doi` | string | DOI of the current (latest) registered version (empty if none) |
| `doi_versions` | object[] | Full version-DOI history, newest first. Each is `{version, doi, commit_sha, is_current, registered_at}` |
| `discipline` | object/null | `{id, name, slug, color_primary}` or `null` if unassigned |
| `author_urls` | object | Map of author name → homepage URL (may be empty `{}`) |
| `github_repo` | string | GitHub repository (e.g. `"OpenChapters/OpenChapters"`) |
| `chapter_subdir` | string | Path within the repo (e.g. `"src/LinearAlgebra"`) |
| `last_updated` | datetime/null | Latest commit date touching this chapter's subdirectory |
| `reviewer_name` | string | Reviewer name (may be empty) |
| `reviewed_at` | datetime/null | Date the chapter was reviewed |
| `html_built_at` | datetime/null | Timestamp of the last successful HTML build (null if no HTML is available) |
| `cached_at` | datetime | Last sync timestamp |
| `has_pdf_labels` | bool | True when a labels-PDF artifact has been built for this chapter (foundational chapters only). See [Get Chapter Labels-PDF](#get-chapter-labels-pdf). |
| `examples_count` | integer | Number of distinct PUBLISHED [worked examples](#worked-examples) tagged to this chapter. List/detail views annotate the queryset; nested or non-list contexts fall back to a per-row count. |

#### Download Chapter Catalog (CSV)

```
GET /api/chapters/catalog.csv
```

Returns all published chapters as a CSV file. No authentication required. Useful for prospective authors who want a complete inventory of the collection without creating an account.

**Columns:** `chabbr, title, discipline, type, authors, last_updated, html_built, examples, url`

**Response (200):** `text/csv; charset=utf-8` with `Content-Disposition: attachment; filename="openchapters-catalog.csv"`. The file begins with a UTF-8 BOM so Excel opens accented characters correctly. Authors are joined with `; `; dates are ISO `YYYY-MM-DD`; `url` is the absolute link to the chapter's detail page.

#### Get Chapter

```
GET /api/chapters/<id>/
```

Returns a single chapter. No authentication required.

**Response (200):** Same structure as a single item in the list response.

#### Get Chapter HTML

```
GET /api/chapters/<id>/html/
GET /api/chapters/<id>/html/<filename>
```

Serves the pre-built HTML representation of a chapter, generated by the `build_chapter_html` pipeline via lwarp. No authentication required.

- The first form returns `node-1.html` (the main chapter content) by default.
- The second form serves individual files from the chapter's HTML output directory (e.g., `node-2.html`, `lwarp_sagebrush.css`, `ImageFolder/figure.svg`).

**Response (200):** The requested HTML, CSS, SVG, or other asset with an appropriate `Content-Type` header. Sets `X-Frame-Options: SAMEORIGIN` so the output can be embedded in the same-origin reader iframe.

**Response (404):** The chapter is not published, has no `chabbr`, or has no HTML output built yet (`html_built_at` is null).

#### Get Chapter Labels-PDF

```
GET /api/chapters/<id>/pdf-labels/
```

Returns the chapter typeset as a standalone PDF with `\usepackage{showkeys}` enabled, so prospective authors can see every `\label{...}` next to its anchor and reference it in their own chapter. Foundational chapters only. No authentication required.

The artifact is rebuilt nightly (when `HTML_BUILD_ENABLED=True`) by the `build_chapter_pdf_labels` task, which the nightly `sync_chapters` task fans out for every published foundational chapter.

**Response (200):** `application/pdf` with `Content-Disposition: attachment; filename="<CHABBR>-labels.pdf"` and `Cache-Control: public, max-age=3600`.

**Response (404):** Chapter is not published, not foundational, has no `chabbr`, or the labels-PDF artifact has not been built yet.

#### Search Chapter Content

```
GET /api/chapters/search/?q=<query>&limit=<n>
```

Full-text search across all published chapters that have an HTML version available. Searches both section headings (weighted higher) and body text, returning ranked results with highlighted snippets. No authentication required.

**Query parameters:**

| Param | Default | Description |
|---|---|---|
| `q` | (required) | Search query. By default each whitespace-separated token is matched as a prefix (typing `sym` finds `symbol`, `symmetry`, `symmetric`). When the query contains a quoted phrase, an `OR` operator, or a `-` exclusion, it falls back to PostgreSQL `websearch` syntax (no prefix expansion). |
| `limit` | `20` | Maximum number of results to return (max 100). |

**Response (200):**

```json
{
  "count": 2,
  "results": [
    {
      "chapter_id": 9,
      "chapter_title": "Number Systems",
      "chabbr": "NUMSYS",
      "discipline": {
        "name": "Materials Science and Engineering",
        "color_primary": "#2563eb"
      },
      "section_title": "1.3 Quaternions",
      "snippet": "<mark>quaternion</mark> is a four-dimensional extension of complex numbers...",
      "read_url": "/chapters/9/read?node=node-1.html#autosec-16"
    }
  ]
}
```

Queries shorter than 2 characters return an empty result list. The `<mark>` tags in snippets are safe to inject directly into HTML for highlighting.

---

### Books

All book endpoints require authentication.

#### List Books

```
GET /api/books/
```

Returns the authenticated user's books (all statuses).

**Response (200):**
```json
{
  "count": 2,
  "results": [
    {
      "id": 1,
      "title": "My Custom Textbook",
      "status": "draft",
      "created_at": "2026-03-25T15:50:00Z",
      "updated_at": "2026-03-25T16:10:00Z"
    }
  ]
}
```

#### Create Book

```
POST /api/books/
```

**Request body:**
```json
{
  "title": "My Custom Textbook"
}
```

**Response (201):**
```json
{
  "id": 1,
  "title": "My Custom Textbook",
  "status": "draft",
  "created_at": "2026-03-25T15:50:00Z",
  "updated_at": "2026-03-25T15:50:00Z",
  "parts": [],
  "build_job": null
}
```

#### Get Book Detail

```
GET /api/books/<id>/
```

Returns the book with all parts, chapters, and build job status.

**Response (200):**
```json
{
  "id": 1,
  "title": "My Custom Textbook",
  "status": "draft",
  "created_at": "2026-03-25T15:50:00Z",
  "updated_at": "2026-03-25T16:10:00Z",
  "parts": [
    {
      "id": 1,
      "title": "Part I: Foundations",
      "order": 0,
      "chapters": [
        {
          "id": 10,
          "order": 0,
          "chapter_detail": {
            "id": 5,
            "title": "Concepts of Linear Algebra",
            "authors": ["Marc De Graef"],
            "..."
          }
        }
      ]
    }
  ],
  "build_job": null
}
```

#### Update Book

```
PATCH /api/books/<id>/
```

**Request body:**
```json
{
  "title": "New Title",
  "doi": "10.1234/openchapters.2026",
  "include_examples": true,
  "include_solutions": true
}
```

All fields are optional in a PATCH request.

- `include_examples` (bool, default True) — when set, builds of this book append a "Worked examples" section after each tagged chapter using the published [examples corpus](#worked-examples). Cross-chapter examples render once, under the earliest tagged chapter in the book.
- `include_solutions` (bool, default True) — when off (and `include_examples` is on), statements appear without solutions, producing a problem-only handout from the same corpus. Ignored when `include_examples` is off.

The book detail response also exposes a derived `examples_count` (distinct PUBLISHED examples tagged to any chapter in the book) for the builder UI to surface.

**Response (200):** Updated book object (includes `has_cover_image` boolean).

#### Delete Book

```
DELETE /api/books/<id>/
```

**Response:** `204 No Content`

#### Upload Cover Image

```
POST /api/books/<book_id>/cover/
Content-Type: multipart/form-data
```

Upload a custom cover page PDF. Must be `.pdf`, max 50MB. Replaces any existing cover.

**Form field:** `cover_image` — the PDF file.

**Response (200):**
```json
{
  "detail": "Cover image uploaded.",
  "has_cover_image": true
}
```

#### Remove Cover Image

```
DELETE /api/books/<book_id>/cover/
```

Removes the uploaded cover image. The book reverts to the default cover.

**Response (200):**
```json
{
  "detail": "Cover image removed.",
  "has_cover_image": false
}
```

---

### Parts

All part endpoints require authentication. The user must own the book.

#### Add Part

```
POST /api/books/<book_id>/parts/
```

**Request body:**
```json
{
  "title": "Part II: Advanced Topics",
  "order": 1
}
```

**Response (201):**
```json
{
  "id": 2,
  "title": "Part II: Advanced Topics",
  "order": 1,
  "chapters": []
}
```

#### Update Part

```
PATCH /api/books/<book_id>/parts/<part_id>/
```

**Request body:**
```json
{
  "title": "Renamed Part"
}
```

**Response (200):** Updated part object.

#### Delete Part

```
DELETE /api/books/<book_id>/parts/<part_id>/
```

Deletes the part and all its chapter assignments.

**Response:** `204 No Content`

#### Reorder Parts

```
PATCH /api/books/<book_id>/parts/reorder/
```

**Request body:**
```json
{
  "order": [3, 1, 2]
}
```

The `order` array contains Part IDs in the desired sequence. Each part's `order` field is set to its index (0-based).

**Response (200):**
```json
{
  "detail": "Parts reordered."
}
```

---

### Book Chapters

Manage chapters within a book part. All endpoints require authentication.

#### Add Chapter to Part

```
POST /api/books/<book_id>/parts/<part_id>/chapters/
```

**Request body:**
```json
{
  "chapter_id": 5,
  "order": 0
}
```

- `chapter_id` — the catalog chapter ID
- `order` — position within the part (0-based)

**Response (201):**
```json
{
  "id": 10,
  "order": 0,
  "chapter_detail": {
    "id": 5,
    "title": "Concepts of Linear Algebra",
    "..."
  }
}
```

**Note:** The `order` value must not collide with an existing chapter in the same part. Use `max(existing orders) + 1` to append safely.

#### Remove Chapter from Part

```
DELETE /api/books/<book_id>/parts/<part_id>/chapters/<bookchapter_id>/
```

The `bookchapter_id` is the ID of the BookChapter association (returned as `id` when adding), not the catalog chapter ID.

**Response:** `204 No Content`

#### Reorder Chapters

```
PATCH /api/books/<book_id>/parts/<part_id>/chapters/reorder/
```

**Request body:**
```json
{
  "order": [12, 10, 11]
}
```

The `order` array contains BookChapter IDs in the desired sequence. Each item's `order` field is set to its index in the array (0-based).

**Response (200):**
```json
{
  "detail": "Reordered."
}
```

---

### Build

#### Trigger Build

```
POST /api/books/<book_id>/build/
```

Enqueues a Celery task to typeset the book. The build format is selected via the request body:

**Body (JSON):**
```json
{ "format": "pdf" }          // default: build as PDF
{ "format": "html" }         // build as lwarp HTML + zip archive
{ "format": "both" }         // chain: PDF first, then HTML
```

The body can additionally carry `include_examples` and `include_solutions` overrides; both default to the values currently stored on the Book and are persisted before the task is launched, so a Retry replays the same settings without resending the body:

```json
{
  "format": "pdf",
  "include_examples": true,
  "include_solutions": false
}
```

See [Worked Examples](#worked-examples) for what these flags do at build time.

A `preview_structure` flag enqueues a slimmer build that renders only the title page, table of contents, and chapter headings (no chapter body, no bibliography, no examples). Useful for verifying part/chapter order without paying for a full typeset.

```json
{ "format": "pdf", "preview_structure": true }
```

`preview_structure` is only valid with `format: "pdf"`. Preview builds skip email delivery and the HTML auto-chain.

**Response (202):**
```json
{
  "detail": "Build queued.",
  "book_id": 1,
  "format": "html"
}
```

**Errors:**
- `400` — invalid `format` value, or `preview_structure: true` paired with a non-PDF format
- `409` — a build is already in progress for this book

#### Get Build Status

```
GET /api/books/<book_id>/build/status/
```

Returns the current build status. Poll this endpoint every few seconds while the status is `queued` or `building`.

**Response (200):**
```json
{
  "status": "complete",
  "build_job": {
    "celery_task_id": "a1b2c3d4-...",
    "started_at": "2026-03-25T16:05:30Z",
    "finished_at": "2026-03-25T16:06:45Z",
    "pdf_path": "/app/media/pdfs/book_1_fbae76f2.pdf",
    "error_message": ""
  }
}
```

**Build job fields:**

| Field | Type | Description |
|---|---|---|
| `celery_task_id` | string | Celery task ID |
| `started_at` | datetime | When the build started |
| `finished_at` | datetime | When the build completed (success or failure) |
| `pdf_path` | string | Filesystem path to the generated PDF |
| `error_message` | string | Error description (empty on success) |

**Status values:**

| Status | Description |
|---|---|
| `draft` | No build has been requested |
| `queued` | Build is waiting to start |
| `building` | LaTeX typesetting in progress |
| `complete` | PDF generated successfully |
| `failed` | Build failed; see `error_message` |

---

### Library

#### List Completed Books

```
GET /api/library/
```

Returns the authenticated user's books that have any completed output — either PDF (`status = complete`) or HTML (`html_built_at` set).

**Response (200):**
```json
{
  "count": 1,
  "results": [
    {
      "id": 1,
      "title": "My Custom Textbook",
      "status": "complete",
      "created_at": "2026-03-25T15:50:00Z",
      "updated_at": "2026-03-25T16:06:45Z",
      "html_built_at": "2026-03-25T16:10:12Z",
      "has_pdf": true,
      "has_html": true
    }
  ]
}
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `has_pdf` | bool | True when a PDF build exists on disk |
| `has_html` | bool | True when an HTML build exists on disk |
| `html_built_at` | datetime \| null | When HTML was last built |

---

### Community Library

Public, listing-only catalog of completed books from users who set `share_builds=true` on their profile. No PDF or HTML downloads are exposed; the recommended way to use a shared book is to clone its structure into a new draft of your own.

#### List Public Books

```
GET /api/library/public/
```

Returns the most recently updated completed books from opted-in users. No authentication required. Not paginated.

**Response (200):**
```json
[
  {
    "id": 12,
    "title": "Symmetry and Diffraction Primer",
    "author_display": "Marc De Graef",
    "updated_at": "2026-04-30T17:21:09Z",
    "parts": [
      {
        "title": "Part I",
        "order": 0,
        "chapters": [
          { "id": 5,  "title": "Concepts of Linear Algebra", "chabbr": "LINALG" },
          { "id": 9,  "title": "Number Systems",             "chabbr": "NUMSYS" }
        ]
      }
    ]
  }
]
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `id` | integer | Book id (used by the clone endpoint) |
| `title` | string | User-defined book title |
| `author_display` | string | The owner's `full_name`, falling back to `"Anonymous"` when unset. Email is never exposed. |
| `updated_at` | datetime | When the book was last completed/rebuilt |
| `parts[]` | array | Ordered parts; each contains an ordered list of chapter references |
| `parts[].chapters[]` | array | `{id, title, chabbr}` per chapter — slim payload, no descriptions or TOC |

#### Clone a Public Book

```
POST /api/library/public/<id>/clone/
```

Creates a new **draft** book under the requesting user's account, with the source book's parts and chapter references duplicated in their original order. **Requires authentication.**

**Not copied:** cover image, DOI, build artifacts, build job history. The new title is `"Copy of <source title>"`. The cloned book starts in `draft` status, ready to edit and build under the cloning user's identity.

**Response (201):**
```json
{ "id": 47 }
```
The new book's id, suitable for routing to `/books/<id>` in the editor.

**Response (404):** Source book id does not exist, the source owner has not opted in (`share_builds=false`), or the source is not in `complete` status.

---

### Worked Examples

A community-contributed corpus of LaTeX problems with solutions, each tagged to one or more chapters. See the [user guide](user-guide.md#worked-examples) for the user-facing flow and the [admin guide](admin-guide.md#worked-examples) for the moderation workflow.

The full Example schema (returned by detail and admin endpoints):

| Field | Type | Description |
|---|---|---|
| `id` | integer | Unique identifier. |
| `primary_chapter` | object | `{id, title, chabbr}` — the chapter whose preamble drives snippet preview compiles, and which determines book-build placement when more than one tagged chapter is in the same book. |
| `chapters` | object[] | All tagged chapters (one or more). Each is `{id, title, chabbr}`. |
| `statement_tex` | string | LaTeX source for the problem. |
| `solution_tex` | string | LaTeX source for the solution. |
| `difficulty` | string | `"introductory"`, `"standard"`, or `"advanced"`. |
| `license` | string | License string, defaults to `"CC BY-NC-SA 4.0"`. |
| `status` | string | `"draft"`, `"pending"`, `"published"`, or `"rejected"`. |
| `rejection_reason` | string | Empty unless `status="rejected"`. Cleared automatically when the author edits the example. |
| `author_display` | string | Author's full name; falls back to `"Anonymous"` when blank. |
| `preview_built_at` | datetime/null | Set when the snippet preview compile last succeeded. |
| `preview_build_log` | string | Last 8 KB of arara output captured on the most recent failed build. Empty after a successful build. |
| `preview_fresh` | bool | True iff `preview_built_at >= updated_at`. The submit endpoint enforces the same invariant. |
| `preview_pdf_url` | string/null | Short-lived signed URL for the cached preview PDF (TTL 30 minutes); for PUBLISHED examples the URL is unsigned and anonymous-readable. Null when no preview has been built. |
| `created_at`, `updated_at` | datetime | `updated_at` reflects the last *content* edit; status transitions (submit / approve / reject) do not bump it, so the freshness check is not invalidated by a state change. |

The list serializer omits `solution_tex` and the preview-related fields (the public list never shows solutions).

#### List Examples

```
GET /api/examples/
```

Returns published examples. No authentication required; pagination matches the chapter list.

**Query parameters:**

- `page` — page number (default 1).
- `chapter` — filter by `chabbr` (matches any tagged chapter, not just primary).
- `difficulty` — `introductory` / `standard` / `advanced`.
- `search` — case-insensitive substring match against `statement_tex` and `solution_tex`.

**Response (200):** paginated list of examples (slim shape, no `solution_tex`).

#### Get Example

```
GET /api/examples/<id>/
```

Returns a published example. No authentication required. 404 when the example exists but is not in `published` status — authors should fetch their own non-published examples via the `manage` endpoint instead.

**Response (200):** Full example object including `solution_tex`, `preview_pdf_url`, and `preview_build_log`.

#### Get / Manage Own Example

```
GET    /api/examples/<id>/manage/
PATCH  /api/examples/<id>/manage/
DELETE /api/examples/<id>/manage/
```

Authenticated. Operates on the caller's own example regardless of status; 404 for examples owned by anyone else.

- `GET` returns the same shape as the public detail endpoint, including `preview_build_log` and a signed `preview_pdf_url`.
- `PATCH` accepts the writable subset of the schema (`primary_chapter`, `chapters`, `statement_tex`, `solution_tex`, `difficulty`). Allowed only on `draft` and `rejected` examples; editing a `rejected` example moves it back to `draft` and clears `rejection_reason` automatically.
- `DELETE` requires the example to be in `draft` status.

#### List Own Examples

```
GET /api/examples/mine/
```

Authenticated. Returns the caller's examples across all statuses. Used by the **My worked examples** section on the profile page.

#### Create Example

```
POST /api/examples/
```

Authenticated. Creates the example in `draft` status with the caller as author.

**Request body:**

```json
{
  "primary_chapter": 5,
  "chapters": [5, 15],
  "statement_tex": "Let $A$ be a $3\\times 3$ symmetric matrix...",
  "solution_tex": "Since $A$ is symmetric...",
  "difficulty": "standard"
}
```

**Validation:**

- `chapters` — at least one entry required.
- `primary_chapter` — must be one of the entries in `chapters`.
- `statement_tex`, `solution_tex` — both must be non-blank.

**Response (201):** Full example object (detail shape).

#### Trigger Preview Build

```
POST /api/examples/<id>/preview/
```

Authenticated. The author of the example or any staff user can trigger a rebuild. Enqueues a Celery task that compiles the snippet on the worker.

**Response (202):**

```json
{ "task_id": "9ba9aa74-db73-4d79-8c97-549858380316" }
```

The frontend polls the `manage` endpoint after dispatch; when `preview_built_at` advances, the new PDF is ready. When the compile fails, `preview_build_log` is populated and `preview_built_at` is unchanged.

**Errors:** `404` for non-author callers; `404` if the example does not exist.

#### Get Preview PDF

```
GET /api/examples/<id>/preview.pdf[?t=<signed-token>]
```

Serves the cached snippet preview PDF. Authorization, in order:

1. PUBLISHED examples are anonymous-readable.
2. A valid `t` token is admitted regardless of status. Tokens are minted by the detail / list serializers as part of `preview_pdf_url` (TTL 30 minutes).
3. Otherwise: author or staff via JWT.

Anything else returns `404`.

The frontend always uses the URL from `preview_pdf_url` rather than constructing its own — that keeps iframes, anchor tags, and `window.open` calls authorized without needing a JWT in the URL.

**Response (200):** `application/pdf`, `Content-Disposition: inline`, `X-Frame-Options: SAMEORIGIN` (so the editor's iframe can render).

**Response (404):** Example missing, not authorized, or the artifact has not been built yet.

#### Submit for Review

```
POST /api/examples/<id>/submit/
```

Authenticated. Moves a `draft` or `rejected` example to `pending`.

Requires `preview_built_at >= updated_at` — i.e., the snippet must have a successful preview compile newer than the most recent edit. The frontend disables the submit button when this invariant fails; the server returns `400` with a hint to re-run Preview.

**Response (200):** Full example object (now in `pending` status).

#### Revision History

```
GET /api/examples/<id>/versions/
```

Returns the prior-state ledger for an example, newest first. Visible to the author of the example and to any staff user; everyone else gets `404` (kept the same as a missing example to avoid leaking existence).

**Response (200):**
```json
[
  {
    "version_no": 2,
    "created_at": "2026-05-09T18:21:03Z",
    "editor_display": "Jane Doe",
    "snapshot": {
      "statement_tex": "...",
      "solution_tex": "...",
      "difficulty": "standard",
      "primary_chapter_chabbr": "BASCRY",
      "chapters_chabbrs": ["BASCRY", "DIFCAL"],
      "status": "published",
      "slug": null
    }
  }
]
```

`editor_display` is the name of the user whose edit produced the next version (or `null` if unattributed). A version row is written every time an author saves a change to a non-draft example; drafts edit in place. An example that has never been edited returns `[]`, not `404`.

#### Admin: Review Queue

```
GET /api/admin/examples/[?status=pending]
```

Staff only. Returns a non-paginated list filtered by status (`pending` by default, accepts any of the `Status` values).

#### Admin: Approve

```
POST /api/admin/examples/<id>/approve/
```

Staff only. `pending` → `published`. Returns the updated example.

**Errors:** `400` if the example is not in `pending` status; `404` if missing.

#### Admin: Reject

```
POST /api/admin/examples/<id>/reject/
```

Staff only. `pending` → `rejected`. Required body:

```json
{ "rejection_reason": "Please show the determinant expansion step." }
```

The reason is shown to the author at the top of the editor and on the public detail page. The author can edit the example to return it to `draft` and re-submit.

**Errors:** `400` if `rejection_reason` is blank or the example is not in `pending` status; `404` if missing.

---

### Cover Images

#### Get Chapter Cover

```
GET /api/chapters/<id>/cover/
```

Returns the chapter's cover image as a PNG. The image is fetched from GitHub on first request and cached locally on the server. No authentication required.

**Response:** `200 OK` with `Content-Type: image/png` and `Cache-Control: public, max-age=86400`.

Returns `404` if the chapter has no cover image, or `502` if the GitHub fetch fails.

---

### PDF Download

#### Download PDF (Authenticated)

```
GET /api/books/<book_id>/download/
```

Downloads the completed PDF for the authenticated user's book.

**Response:** PDF file with `Content-Disposition: attachment; filename="Book Title.pdf"`.

#### Download PDF (Signed Link)

```
GET /api/dl/<token>/
```

Downloads a PDF using a signed, time-limited token from an email delivery link. No authentication required — the signed token proves the link was issued by the server.

Tokens expire after `PDF_LINK_EXPIRY_DAYS` (default 7 days).

**Response:** PDF file, or `403` if the token is invalid/expired.

---

### Book HTML Output

Per-book HTML (generated with format `html` or `both`) is served from the following endpoints. All require the owning user's JWT.

#### View Book HTML

```
GET /api/books/<book_id>/html/
GET /api/books/<book_id>/html/<path:filename>
```

Serves the lwarp output stored under `media/html_books/book_<id>/`. With no `filename`, the server returns `node-1.html` (first content page) if present, else `index.html`. Path traversal is rejected.

Content types: `.html`, `.css`, `.svg`, `.png`, `.txt` (guessed otherwise). The response sets `X-Frame-Options: SAMEORIGIN` so the frontend can embed the output in an iframe.

Returns `404` if no HTML build exists for the book.

#### Download Book HTML (zip)

```
GET /api/books/<book_id>/download-html/
```

Streams the pre-built `book.zip` (archive of the full HTML site: pages, CSS, SVG figures, MathJax config). The zip is created during the build and stored alongside the HTML files, so requests are O(1).

**Response:** Zip file with `Content-Disposition: attachment; filename="Book Title.zip"`, or `404` if no HTML archive exists.

---

### Health Check

#### Check Service Health

```
GET /api/health/
```

Returns the health status of the platform. No authentication required. Used by Docker healthchecks and load balancers.

**Response (200):**
```json
{
  "status": "ok",
  "database": "ok"
}
```

**Response (503):** returned when the database is unreachable:
```json
{
  "status": "error",
  "database": "error: connection refused"
}
```

---

## Example: Full Workflow

```bash
# 1. Register
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepass123"}'

# 2. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepass123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")

AUTH="Authorization: Bearer $TOKEN"

# 3. Browse chapters
curl -s http://localhost:8000/api/chapters/ | python3 -m json.tool

# 4. Create a book
BOOK_ID=$(curl -s -X POST http://localhost:8000/api/books/ \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"title": "My Textbook"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 5. Add a part
PART_ID=$(curl -s -X POST http://localhost:8000/api/books/$BOOK_ID/parts/ \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"title": "Part I", "order": 0}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 6. Add chapters to the part (use chapter IDs from step 3)
curl -X POST http://localhost:8000/api/books/$BOOK_ID/parts/$PART_ID/chapters/ \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"chapter_id": 5, "order": 0}'

curl -X POST http://localhost:8000/api/books/$BOOK_ID/parts/$PART_ID/chapters/ \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"chapter_id": 15, "order": 1}'

# 7. Trigger build
curl -X POST http://localhost:8000/api/books/$BOOK_ID/build/ \
  -H "$AUTH"

# 8. Poll build status
curl -s http://localhost:8000/api/books/$BOOK_ID/build/status/ \
  -H "$AUTH" | python3 -m json.tool
```
