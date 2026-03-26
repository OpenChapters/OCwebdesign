# OpenChapters API Reference

The OpenChapters API is a RESTful JSON API built with Django REST Framework. All endpoints are served under the `/api/` prefix.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Pagination](#pagination)
3. [Error Responses](#error-responses)
4. [Endpoints](#endpoints)
   - [Auth](#auth)
   - [Password Reset](#password-reset)
   - [Profile](#profile)
   - [Chapters](#chapters)
   - [Books](#books)
   - [Parts](#parts)
   - [Book Chapters](#book-chapters)
   - [Build](#build)
   - [Library](#library)
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

Always returns success regardless of whether the email exists (prevents email enumeration). The reset link is sent via SendGrid in production, or logged to the server console in development.

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
  "is_staff": false,
  "date_joined": "2026-03-25T15:50:00Z",
  "last_login": "2026-03-26T10:30:00Z"
}
```

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

### Chapters

#### List Chapters

```
GET /api/chapters/
```

Returns all published chapters. No authentication required.

**Query parameters:**
- `page` — page number (default: 1)

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
| `depends_on` | string[] | List of `chabbr` values this chapter cross-references |
| `github_repo` | string | GitHub repository (e.g. `"OpenChapters/OpenChapters"`) |
| `chapter_subdir` | string | Path within the repo (e.g. `"src/LinearAlgebra"`) |
| `cached_at` | datetime | Last sync timestamp |

#### Get Chapter

```
GET /api/chapters/<id>/
```

Returns a single chapter. No authentication required.

**Response (200):** Same structure as a single item in the list response.

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
  "title": "New Title"
}
```

**Response (200):** Updated book object.

#### Delete Book

```
DELETE /api/books/<id>/
```

**Response:** `204 No Content`

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

Enqueues a Celery task to typeset the book as a PDF.

**Response (202):**
```json
{
  "detail": "Build queued.",
  "book_id": 1
}
```

**Errors:**
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

Returns only books with status `complete` for the authenticated user.

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
      "updated_at": "2026-03-25T16:06:45Z"
    }
  ]
}
```

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
