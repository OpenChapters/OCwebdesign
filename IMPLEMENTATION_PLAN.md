# OpenChapters Web — Implementation Plan

## Stack Summary

| Layer | Technology |
|---|---|
| Backend framework | Python / Django |
| Async job queue | Celery + Redis |
| Database | PostgreSQL |
| Frontend | React (Vite) |
| GitHub data | GitHub REST API v3 |
| Email delivery | SendGrid |
| File storage | AWS S3 (or local for dev) |
| Local dev environment | Docker + docker-compose |
| Production server | nginx + gunicorn |

---

## Phase 1 — Project Foundation

**Goal**: Running local dev environment with no application logic yet.

### Tasks
1. Initialize Django project (`django-admin startproject ocweb`)
2. Create `docker-compose.yml` with services: `web` (Django), `db` (PostgreSQL), `redis` (Redis), `worker` (Celery)
3. Configure Django settings for dev vs. production (environment variables via `python-decouple` or `django-environ`)
4. Connect Django to PostgreSQL
5. Configure Celery with Redis as broker
6. Add a `Makefile` with shortcut commands: `make dev`, `make migrate`, `make worker`, `make shell`
7. Set up a basic Django admin site

### Deliverable
`docker-compose up` starts all services; Django admin is reachable at `/admin`.

---

## Phase 2 — Data Models

**Goal**: Define the core database schema.

### Chapter Repo File Convention

Each chapter GitHub repo must contain a `chapter.json` at its root:

```json
{
  "title": "Introduction to Calculus",
  "authors": ["Jane Smith"],
  "toc": [
    "1. Limits and Continuity",
    "2. Derivatives",
    "3. Integration"
  ],
  "entry_file": "calc01.tex",
  "cover_image": "cover.png",
  "keywords": ["calculus", "mathematics"]
}
```

The repo structure expected by the build pipeline:

```
<chapter-repo>/
  chapter.json          # machine-readable metadata (title, TOC, authors, etc.)
  cover.png             # cover image shown in the chapter browser
  src/
    <chaptername>.tex   # LaTeX source (entry_file value in chapter.json)
    chaptercitations.bib
    eps/                # EPS figures (editable originals)
    pdf/                # PDF versions of all figures (used by pdflatex at build time)
```

> **Figure convention**: each chapter repo stores both EPS (source) and PDF versions of
> all figures. `pdflatex` uses the `pdf/` copies directly, avoiding costly `epstopdf`
> conversion at build time.

### Models

```
Chapter
  github_repo       CharField        # e.g. "OpenChapters/chapter-calculus-01"
  title             CharField
  authors           JSONField        # list of author name strings
  description       TextField
  toc               JSONField        # list of section headings from chapter.json
  cover_image_url   URLField         # cover.png served from GitHub raw URL
  latex_entry_file  CharField        # e.g. "src/calc01.tex"
  keywords          JSONField        # list of keyword strings
  cached_at         DateTimeField

User (extend Django AbstractUser)
  email             (required, used for PDF delivery)

Book (user's in-progress or completed assembly)
  user              ForeignKey(User)
  title             CharField
  created_at        DateTimeField
  status            CharField        # draft | queued | building | complete | failed

BookPart
  book              ForeignKey(Book)
  title             CharField
  order             IntegerField

BookChapter
  part              ForeignKey(BookPart)
  chapter           ForeignKey(Chapter)
  order             IntegerField

BuildJob
  book              OneToOneField(Book)
  celery_task_id    CharField
  started_at        DateTimeField
  finished_at       DateTimeField
  pdf_path          CharField        # S3 key or local path
  log_output        TextField
  error_message     TextField
```

### Tasks
1. Create a `catalog` Django app (chapters) and a `books` app (assembly + builds)
2. Write and apply migrations
3. Register all models in Django admin for manual inspection

### Deliverable
All tables exist; chapters and books can be created/inspected via admin.

---

## Phase 3 — GitHub Chapter Catalog

**Goal**: Populate the chapter catalog from the OpenChapters GitHub organization.

### Design
- A management command (`python manage.py sync_chapters`) hits the GitHub API, fetches `chapter.json` from each repo's root, and upserts `Chapter` records.
- A scheduled Celery Beat task runs `sync_chapters` nightly to pick up new or updated chapters.
- `cover_image_url` is set to the raw GitHub URL for `cover.png` in each repo.

### Tasks
1. Create a `github_client.py` service module wrapping `httpx` or `requests` for GitHub API calls (authenticated with a GitHub token to avoid rate limits)
2. Write `sync_chapters` management command — fetch `chapter.json` via the GitHub Contents API, parse all fields, upsert `Chapter` records
3. Add Celery Beat schedule for nightly sync
4. Handle pagination (GitHub returns max 100 repos per page)
5. Log and skip repos that are missing `chapter.json` rather than failing the whole sync

### Deliverable
Running `sync_chapters` populates the `Chapter` table; chapters are visible in admin.

---

## Phase 4 — Book Assembly & LaTeX Build Pipeline

**Goal**: Turn a user's chapter selection into a typeset PDF.

### Design

#### `build_request.json` — web-to-pipeline interface
The web backend writes this file to describe what to build. The Python build scripts read it.
This replaces the previously unused `ChapterTitles.txt`. It maps directly to the `Book` /
`BookPart` / `BookChapter` database models.

```json
{
  "book_title": "Introduction to Engineering Mathematics",
  "parts": [
    {
      "title": "Calculus",
      "chapters": [
        { "repo": "OpenChapters/chapter-calc01", "entry_file": "src/calc01.tex" }
      ]
    },
    {
      "title": "Linear Algebra",
      "chapters": [
        { "repo": "OpenChapters/chapter-linAlg01", "entry_file": "src/linAlg01.tex" }
      ]
    }
  ]
}
```

#### Build scripts (`Build/scripts/`)
All arara helper logic previously defined in `.bashrc` functions is replaced with
standalone Python scripts. These are version-controlled, containerization-friendly,
and testable in isolation without a running web server.

```
Build/scripts/
  build_main_tex.py     # reads build_request.json, renders main.tex via Jinja2 template
  concat_bibs.py        # concatenates all selected chapter .bib files into OpenChapters.bib
  collect_images.py     # copies PDF figures from each chapter's pdf/ folder into ImageFolder/
  generate_gin.py       # writes a synthetic gitHeadLocal.gin so gitinfo2 works without a real .git/
  main.tex.j2           # Jinja2 template for the generated main.tex
```

Each script accepts explicit CLI arguments (e.g. `python concat_bibs.py --workdir /tmp/ocbuild-<uuid>`)
so arara directives are self-contained and reproducible.

#### Per-request isolated build workspace
The `Build/` folder in the repo is treated as a **template only** — never written to during
a live build. Each Celery build task creates a fresh temp directory, eliminating build
collisions and supporting concurrent requests.

No symlinks are used. `build_main_tex.py` writes all `\input{}` and `\graphicspath{}`
directives as absolute paths resolved at build time, pointing directly into the cloned
chapter repos within the temp workspace.

#### Build pipeline (Celery task)
```
build_book(book_id)
  1. Create isolated temp directory: /tmp/ocbuild-<uuid>/
  2. Copy .sty, .ins, .ist files and matter/ from Build/ template into temp dir
  3. Write build_request.json to temp dir
  4. Clone each required chapter repo into temp dir subdirectories
  5. Run concat_bibs.py    → produces OpenChapters.bib
  6. Run collect_images.py → copies PDF figures into ImageFolder/
  7. Run build_main_tex.py → renders main.tex from main.tex.j2 template
  8. Run generate_gin.py   → writes synthetic gitHeadLocal.gin (build UUID + timestamp)
  9. Run arara on main.tex via subprocess (with Celery time_limit timeout)
 10. On success: upload PDF to S3, update BuildJob.pdf_path, set Book.status = complete
 11. On failure: capture full arara log output, set Book.status = failed
 12. Clean up temp directory
 13. Trigger deliver_pdf task
```

### Tasks
1. Write `Build/scripts/main.tex.j2` Jinja2 template (see template spec below)
2. Write `Build/scripts/build_main_tex.py` — reads `build_request.json`, renders `main.tex.j2`
3. Write `Build/scripts/concat_bibs.py`
4. Write `Build/scripts/collect_images.py`
5. Write `Build/scripts/generate_gin.py` — writes synthetic `gitHeadLocal.gin` so `gitinfo2` works without a real `.git/` directory; populates `shash`/`lhash` from build UUID, `authsdate` from build timestamp, `reltag` as `web-<YYYY-MM-DD>`; resulting page footer reads: `[OpenChapters Web Build] Branch: web-build @ <short-uuid> • Release: web-<date> (<date>)`
6. Write `build_book` Celery task implementing the pipeline above
5. Write `deliver_pdf` Celery task (sends email via SendGrid with a signed S3 URL)
6. Build the `worker` Docker image based on `texlive/texlive:latest` (full installation) with arara and Python 3 — see Docker image notes below; **prototype this image first** as it is the heaviest and riskiest dependency
7. Add Celery `time_limit` to `build_book` to handle arara hangs
8. Store full arara log in `BuildJob.log_output` for debugging failed builds

> **Prototype first**: build and test the worker Docker image and the three build scripts
> against a real chapter repo *before* wiring them into the web framework. This is the
> highest-risk component and the most likely source of unexpected failures.

### Worker Docker Image Notes

**Base image**: `texlive/texlive:latest` (full TeX Live installation, ~5 GB). A hand-picked
subset is not recommended — the package list is broad enough (tikz, tcolorbox, forest,
comfortaa, adforn, biblatex + biber, SIunits, etc.) that a partial install will cause
hard-to-debug missing-package failures mid-build.

**Additional requirements** in the worker image:
- `arara` (build tool)
- `biber` (backend for `biblatex`)
- Python 3 + pip (for the build scripts)
- `Jinja2`, `httpx` Python packages (for `build_main_tex.py` and GitHub access)
- Git (for cloning chapter repos)

**Package issues to resolve before first build**:

| Package | Issue | Resolution |
|---|---|---|
| `gitinfo2` | Reads `.git/` hooks at compile time; fails in a temp build directory with no real git history | **Resolved**: `generate_gin.py` writes a synthetic `gitHeadLocal.gin` before arara runs. The `[local]` package option reads this file directly; no `.git/` directory is needed. The arara `copy` directive is omitted from the generated `main.tex`. |
| ~~`SIunits`~~ | ~~Deprecated; may produce errors on current TeX Live~~ | **Resolved**: replaced by `siunitx` in `OpenChapters.sty`. |
| `epsfig` | Legacy EPS inclusion; `pdflatex` cannot include EPS directly | Confirmed workaround: use PDF figures from each chapter's `pdf/` folder; `epsfig` can remain as a compatibility shim |
| `mytodonotes` | Custom local `.sty` — not on CTAN | Must be copied from `Build/` template into every temp build directory alongside the other `.sty` files |
| `arara.sty` | Custom local `.sty` | Same as above — copy from `Build/` template |

### Deliverable
Triggering a build job for a manually created Book record produces a PDF and sends an email.

---

## Phase 5 — REST API

**Goal**: Expose all data and actions the frontend needs.

### Endpoints

```
GET  /api/chapters/                   list all chapters (title, icon, toc preview)
GET  /api/chapters/<id>/              chapter detail

POST /api/auth/register/
POST /api/auth/login/
POST /api/auth/logout/

GET  /api/books/                      list user's books
POST /api/books/                      create new book (title)
GET  /api/books/<id>/                 book detail with parts and chapters
PUT  /api/books/<id>/                 update book title
DELETE /api/books/<id>/

POST /api/books/<id>/parts/           add a part
PUT  /api/books/<id>/parts/<pid>/     rename / reorder part
DELETE /api/books/<id>/parts/<pid>/

POST /api/books/<id>/parts/<pid>/chapters/     add chapter to part
DELETE /api/books/<id>/parts/<pid>/chapters/<cid>/
POST /api/books/<id>/parts/<pid>/chapters/reorder/

POST /api/books/<id>/build/           enqueue build job
GET  /api/books/<id>/build/status/    poll build status + log tail

GET  /api/library/                    user's completed books with download links
```

### Tasks
1. Install Django REST Framework
2. Implement serializers and viewsets for each resource
3. Use DRF token auth or JWT (`djangorestframework-simplejwt`)
4. Add pagination to chapter list
5. Return signed S3 URLs (expiring links) for PDF downloads

### Deliverable
All endpoints testable via curl or Postman; frontend can be built against these.

---

## Phase 6 — Frontend (React)

**Goal**: Build the user-facing UI.

### Views

| View | Description |
|---|---|
| Chapter Browser | Grid of chapter cards with icon; hover shows TOC popover |
| Book Editor | Sidebar cart; drag-and-drop chapter ordering into parts; set book/part titles |
| Checkout | Review selection, confirm title, submit build |
| Build Status | Polling progress indicator, log output on failure |
| Library | List of user's completed books with download buttons |
| Auth | Login / Register pages |

### Tasks
1. Scaffold with Vite + React + TypeScript
2. Set up React Router for view routing
3. Configure API client (Axios or `fetch` wrapper) pointing to Django backend
4. Implement Chapter Browser with hover TOC using a popover component
5. Implement Book Editor with drag-and-drop (`@dnd-kit/core`)
6. Implement build status polling (poll `/api/books/<id>/build/status/` every 3s)
7. Implement Library view
8. Auth flows (login, register, protected routes)
9. Responsive layout (CSS Grid / Tailwind)

### Deliverable
Full end-to-end flow: browse chapters, build a book, receive PDF.

---

## Phase 7 — Production Deployment

**Goal**: Publicly accessible, stable deployment.

### Infrastructure
- **Server**: Single VPS (e.g. DigitalOcean, Hetzner) or AWS EC2 — needs enough RAM for TeX Live (~4 GB)
- **Web**: nginx reverse proxy → gunicorn (Django) + serves React build as static files
- **Worker**: Celery worker process (same server or separate, given LaTeX CPU cost)
- **Database**: Managed PostgreSQL (RDS, DigitalOcean Managed DB) or self-hosted
- **Redis**: Managed Redis or self-hosted
- **Storage**: S3-compatible bucket for PDFs
- **SSL**: Let's Encrypt via Certbot

### Tasks
1. Write production `Dockerfile` for web and worker (worker must include full TeX Live + arara)
2. Write `docker-compose.prod.yml` or Kubernetes manifests
3. Configure nginx with SSL termination and static file serving
4. Set all secrets via environment variables (never in source)
5. Set up database backups
6. Configure SendGrid domain authentication (for email deliverability)
7. Set PDF link expiry policy on S3

### Deliverable
Site live at production domain; full flow works end-to-end.

---

## Development Sequence Summary

```
Phase 1  Foundation & dev environment     ~1 week
Phase 2  Data models                      ~3 days
Phase 3  GitHub chapter sync              ~1 week
Phase 4  LaTeX build pipeline             ~2 weeks  (heaviest engineering work)
Phase 5  REST API                         ~1 week
Phase 6  Frontend                         ~3 weeks
Phase 7  Production deployment            ~1 week
```

The LaTeX/arara pipeline (Phase 4) is the highest-risk component and should be prototyped early, independently of the web framework, to validate that arara can be driven correctly from a Python subprocess with the expected chapter repo structure.

---

## Key Open Questions to Resolve Early

1. **arara directives**: Now resolved. The full sequence from `Build/main.tex` is: `copyImageFiles` → `pdflatex` → `makeindex` → `mergemainbibfiles` → `biber` → `pdflatex` × 2 → cleanup. The generated `main.tex` uses this same sequence, minus the `copy` directive (replaced by `generate_gin.py`). The custom arara rules `copyImageFiles` and `mergemainbibfiles` correspond to `collect_images.py` and `concat_bibs.py` respectively and must be registered as arara rules in the worker Docker image.
2. ~~**Figure migration**~~: Complete. PDF versions of all figures committed into `pdf/` subfolders in each chapter repo.
3. **PDF storage policy**: How long are generated PDFs retained? Are download links public or do they require authentication?
4. **User accounts**: Is registration open to anyone, or invite/approval-based?
5. **Chapter pinning**: Are chapters cloned at HEAD at build time, or pinned to a specific commit/tag for reproducibility? Pinning guarantees the same PDF can be regenerated later; HEAD is always current.
