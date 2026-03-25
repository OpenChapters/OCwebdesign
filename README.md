# OpenChapters Web Platform

A web application for building on-demand, open-source PDF textbooks from LaTeX source chapters. Authors contribute chapters under the [Creative Commons CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) license; users browse the catalog, assemble custom books, and receive professionally typeset PDFs.

## How It Works

1. **Browse** — explore the chapter catalog with hover-to-preview tables of contents
2. **Assemble** — create a book, organize chapters into parts, drag-and-drop to reorder
3. **Build** — submit the book for LaTeX typesetting; the server clones chapter sources, runs the [arara](https://github.com/islandoftex/arara) build pipeline, and produces a PDF
4. **Download** — completed PDFs appear in your personal library

Chapters and figures live in the [OpenChapters/OpenChapters](https://github.com/OpenChapters/OpenChapters) monorepo on GitHub. The chapter catalog is synced nightly from `chapter.json` metadata files in each chapter's subdirectory.

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│  Browser (React / Vite / Tailwind)                         │
│  Chapter browser · Book editor · Build status · Library    │
└──────────────────────────┬─────────────────────────────────┘
                           │ /api/*
┌──────────────────────────▼─────────────────────────────────┐
│  Django + DRF + SimpleJWT                                  │
│  REST API · User auth · Book/Part/Chapter models           │
└────────┬──────────────────────────────────┬────────────────┘
         │                                  │
┌────────▼────────┐              ┌──────────▼──────────┐
│  PostgreSQL 16  │              │  Redis 7            │
│  Data store     │              │  Celery broker      │
└─────────────────┘              └──────────┬──────────┘
                                            │
                              ┌─────────────▼────────────────┐
                              │  Celery Worker               │
                              │  TeX Live + arara + biber    │
                              │  Clones repos, runs pipeline,│
                              │  produces PDF                │
                              └──────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, @dnd-kit, React Query |
| Backend | Django 5.1, Django REST Framework, SimpleJWT |
| Task queue | Celery 5 + Redis |
| Database | PostgreSQL 16 |
| Typesetting | TeX Live 2025+, arara 7, biber |
| Dev environment | Docker Compose |

## Project Structure

```
OCwebdesign/
├── ocweb/                  Django project (settings, urls, wsgi, celery)
│   └── settings/
│       ├── base.py         Shared settings
│       ├── dev.py          Development overrides (DEBUG=True)
│       └── prod.py         Production (whitenoise, secure cookies)
├── users/                  Custom User model (email-based auth)
├── catalog/                Chapter catalog (synced from GitHub)
│   ├── github_client.py    GitHub API wrapper
│   └── management/commands/sync_chapters.py
├── books/                  Book assembly, parts, build pipeline
│   ├── models.py           Book, BookPart, BookChapter, BuildJob
│   ├── tasks.py            Celery tasks (build_book, deliver_pdf)
│   └── views.py            REST API views
├── Build/
│   ├── scripts/            Python build pipeline scripts
│   │   ├── build_main_tex.py     Renders main.tex from Jinja2 template
│   │   ├── concat_bibs.py        Merges chapter bibliographies
│   │   ├── collect_images.py     Collects PDF figures into ImageFolder/
│   │   ├── generate_gin.py       Writes synthetic gitHeadLocal.gin
│   │   └── main.tex.j2           Jinja2 template for main.tex
│   └── template/           LaTeX template files (.sty, .ins, .ist)
├── arara-rules/            Custom arara rule definitions
├── frontend/               React SPA (Vite + TypeScript)
│   └── src/
│       ├── api/            Axios client with JWT interceptors
│       ├── components/     ChapterCard, SortableChapterList, Navbar
│       ├── contexts/       AuthContext
│       ├── pages/          All page components
│       └── types/          TypeScript interfaces
├── docker/
│   ├── web/                Django Dockerfile (dev + prod)
│   ├── worker/             TeX Live + Celery Dockerfile
│   └── nginx/              Production nginx reverse proxy
├── docker-compose.yml      Development environment
├── docker-compose.prod.yml Production environment
├── requirements/
│   ├── base.txt            Core Python dependencies
│   ├── dev.txt             Development dependencies
│   └── prod.txt            Production (+ gunicorn, whitenoise)
└── .env.example            Environment variable template
```

## Getting Started (Development)

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- A GitHub personal access token with read access to the OpenChapters organization

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/OpenChapters/OCwebdesign.git
cd OCwebdesign

# 2. Create your environment file
cp .env.example .env
# Edit .env — set SECRET_KEY, GITHUB_TOKEN, and any other values

# 3. Build and start all services
docker compose up --build -d

# 4. Run database migrations
docker compose exec web python manage.py migrate

# 5. Sync the chapter catalog from GitHub
docker compose exec web python manage.py sync_chapters

# 6. Create a superuser (admin access)
docker compose exec web python manage.py createsuperuser
```

The frontend is available at **http://localhost:5173** and the Django admin at **http://localhost:8000/admin/**.

### Services

| Service | Port | Description |
|---|---|---|
| `frontend` | 5173 | Vite dev server (React SPA) |
| `web` | 8000 | Django API (runserver) |
| `worker` | — | Celery worker (LaTeX builds) |
| `db` | 5432 | PostgreSQL |
| `redis` | 6379 | Redis (Celery broker) |

### Useful Commands

```bash
# View logs
docker compose logs -f web worker

# Run Django management commands
docker compose exec web python manage.py shell
docker compose exec web python manage.py sync_chapters --dry-run

# Restart the worker after changing task code
docker compose restart worker

# Rebuild images after changing Dockerfiles or requirements
docker compose build web worker
```

## Production Deployment

See `docker-compose.prod.yml` and `.env.prod.example` for the production setup.

```bash
# 1. Configure production environment
cp .env.prod.example .env.prod
# Edit .env.prod — set all secrets, domain, database password

# 2. Build and start
docker compose -f docker-compose.prod.yml up --build -d

# 3. Initialize
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
docker compose -f docker-compose.prod.yml exec web python manage.py sync_chapters
```

The production stack uses:
- **nginx** — serves the React SPA, proxies `/api/` and `/admin/` to gunicorn
- **gunicorn** — WSGI server for Django (3 workers)
- **whitenoise** — serves Django static files (admin CSS)
- **Celery** — background LaTeX builds

For SSL, place a reverse proxy (e.g., Caddy or nginx with Let's Encrypt) in front of port 80.

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/register/` | No | Create account |
| `POST` | `/api/auth/login/` | No | Obtain JWT tokens |
| `POST` | `/api/auth/token/refresh/` | No | Refresh access token |
| `GET` | `/api/chapters/` | No | List published chapters |
| `GET` | `/api/chapters/<id>/` | No | Chapter detail |
| `GET` | `/api/books/` | Yes | List user's books |
| `POST` | `/api/books/` | Yes | Create a book |
| `GET` | `/api/books/<id>/` | Yes | Book detail (with parts and chapters) |
| `PATCH` | `/api/books/<id>/` | Yes | Update book title |
| `DELETE` | `/api/books/<id>/` | Yes | Delete a book |
| `POST` | `/api/books/<id>/parts/` | Yes | Add a part |
| `PATCH` | `/api/books/<id>/parts/<pid>/` | Yes | Rename a part |
| `DELETE` | `/api/books/<id>/parts/<pid>/` | Yes | Delete a part |
| `POST` | `/api/books/<id>/parts/<pid>/chapters/` | Yes | Add chapter to part |
| `DELETE` | `/api/books/<id>/parts/<pid>/chapters/<cid>/` | Yes | Remove chapter |
| `PATCH` | `/api/books/<id>/parts/<pid>/chapters/reorder/` | Yes | Reorder chapters |
| `POST` | `/api/books/<id>/build/` | Yes | Start PDF build |
| `GET` | `/api/books/<id>/build/status/` | Yes | Poll build status |
| `GET` | `/api/library/` | Yes | Completed books |

## Chapter Metadata

Each chapter in the [OpenChapters monorepo](https://github.com/OpenChapters/OpenChapters) has a `chapter.json` file:

```json
{
  "title": "Concepts of Linear Algebra",
  "authors": ["Marc De Graef"],
  "description": "",
  "toc": ["Matrices and Linear Equations", "General properties of matrices", "..."],
  "entry_file": "LinearAlgebra.tex",
  "cover_image": "cover.png",
  "keywords": [],
  "chapter_type": "foundational",
  "chabbr": "LINALG",
  "depends_on": [],
  "published": true
}
```

- **chapter_type**: `"foundational"` or `"topical"` — controls grouping in the browser
- **chabbr**: unique abbreviation used in LaTeX `\label`/`\ref` cross-references
- **depends_on**: list of `chabbr` values for foundational chapters this chapter references; the Book Editor auto-suggests including these
- **published**: set to `false` to hide incomplete/template chapters from the catalog

## LaTeX Build Pipeline

When a user triggers a build, the Celery worker:

1. Creates an isolated workspace at `/tmp/ocbuild-<uuid>/`
2. Copies `.sty`, `.ins`, `.ist` template files
3. Writes `build_request.json` from the book's part/chapter structure
4. Clones the OpenChapters monorepo (shallow, `--depth=1`)
5. Copies `matter/` (front matter, post matter) from the clone
6. Runs `concat_bibs.py` → merges chapter bibliographies into `OpenChapters.bib`
7. Runs `collect_images.py` → copies PDF figures into `ImageFolder/`
8. Runs `build_main_tex.py` → renders `main.tex` from the Jinja2 template
9. Runs `generate_gin.py` → writes synthetic `gitHeadLocal.gin` for gitinfo2
10. Runs `arara -w main.tex` → pdflatex, makeindex, biber, pdflatex ×2, cleanup
11. Stores the PDF and updates build status

## License

Content (chapters, figures) is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).

The web platform code in this repository is licensed under the MIT License.
