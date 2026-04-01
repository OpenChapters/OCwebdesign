# Multi-Discipline Support — Implementation Plan

## Overview

Currently, OpenChapters serves a single discipline: Materials Science and Engineering. All chapters belong to this discipline and share a single catalog, build pipeline, and styling. This plan describes how to extend the platform to support multiple disciplines (e.g., Mechanical Engineering, Statistics, Physics) while preserving the existing user experience.

---

## Table of Contents

1. [Design Goals](#design-goals)
2. [Approach: Discipline as a Catalog Dimension](#approach-discipline-as-a-catalog-dimension)
3. [Data Model Changes](#data-model-changes)
4. [Content Organization](#content-organization)
5. [Browse Experience](#browse-experience)
6. [Book Assembly](#book-assembly)
7. [Build Pipeline](#build-pipeline)
8. [Admin Panel](#admin-panel)
9. [Migration Path](#migration-path)
10. [Alternative Approaches Considered](#alternative-approaches-considered)
11. [Implementation Phases](#implementation-phases)

---

## Design Goals

1. **Users can browse chapters by discipline** — a discipline selector on the Browse page filters the catalog
2. **Cross-discipline books are allowed** — a user studying materials science may want a statistics chapter in their book
3. **Each discipline can have its own styling** — different `.sty` files, cover templates, and color themes
4. **Minimal disruption** — existing chapters, books, and users are unaffected during migration
5. **Scalable** — adding a new discipline should not require code changes, only content and configuration

---

## Approach: Discipline as a Catalog Dimension

The recommended approach treats discipline as a **tag on chapters**, not as a separate silo. This is simpler than running separate instances or repos per discipline and allows cross-discipline book assembly.

### Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| One monorepo or many? | **One monorepo per discipline** | Each discipline has its own editors, `.sty` files, and release cycle. A single monorepo for all would create governance conflicts. |
| Shared database? | **Yes** | All disciplines share the same database, user accounts, and build pipeline. |
| Cross-discipline books? | **Yes, allowed** | Users can include chapters from multiple disciplines in a single book. The build pipeline handles this by merging `.sty` files. |
| Discipline-specific styling? | **Yes, optional** | Each discipline can define its own `.sty` overrides, cover template, and color palette. Falls back to the default OpenChapters style. |

---

## Data Model Changes

### New Model: `Discipline`

```python
class Discipline(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=50, unique=True)     # URL-friendly: "mse", "mecheng", "stats"
    description = models.TextField(blank=True)

    # GitHub source for this discipline's chapters
    github_repo = models.CharField(max_length=200)           # e.g. "OpenChapters/MechanicalEngineering"
    github_src_path = models.CharField(max_length=200, default="src")

    # Optional discipline-specific styling
    sty_repo_path = models.CharField(max_length=200, blank=True)  # path to custom .sty in the repo
    cover_template = models.CharField(max_length=200, blank=True) # custom frontmatter template
    color_primary = models.CharField(max_length=7, default="#2563eb")  # hex color for UI theming

    # Display order on the Browse page
    order = models.PositiveIntegerField(default=0)
    published = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]
```

### Changes to `Chapter`

```python
class Chapter(models.Model):
    # Existing fields unchanged...

    # NEW: link to discipline
    discipline = models.ForeignKey(
        "Discipline",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chapters",
    )
```

### Changes to `chapter.json`

Each discipline's chapters include a `discipline` field:

```json
{
  "title": "Introduction to Stress Analysis",
  "discipline": "mecheng",
  "chapter_type": "topical",
  ...
}
```

The `sync_chapters` command maps the `discipline` slug to the `Discipline` model.

---

## Content Organization

### Repository Structure

Each discipline has its own GitHub repository following the same conventions as the existing OpenChapters monorepo:

```
OpenChapters/OpenChapters          → Materials Science (existing)
OpenChapters/MechanicalEngineering → Mechanical Engineering (new)
OpenChapters/Statistics            → Statistics (new)
```

Each repo has the same structure:

```
src/
  ChapterName/
    chapter.json
    ChapterName.tex
    pdf/
    cover.png
Build/
  matter/         → discipline-specific front/post matter
  template/       → discipline-specific .sty overrides (optional)
```

### Shared Resources

Some resources are shared across disciplines:

- **User accounts** — a single user can build books from any discipline
- **Build pipeline** — the same Celery worker handles all disciplines
- **Base `.sty` files** — the core OpenChapters style; discipline-specific `.sty` files override or extend it

---

## Browse Experience

### Discipline Selector

The Chapter Browser page gains a discipline selector at the top:

```
[All Disciplines ▼]  [Materials Science]  [Mechanical Engineering]  [Statistics]
```

- **Tabs or pill buttons** for each published discipline
- **"All Disciplines"** shows chapters from all disciplines (default for new visitors)
- The selected discipline is stored in the URL as a query parameter: `/chapters?discipline=mse`
- Chapter counts update per discipline: "Topical Chapters (8) · Foundational Chapters (4)"

### Visual Differentiation

Each discipline can have a **color accent** (from `Discipline.color_primary`):
- The chapter card border or header gradient uses the discipline color
- A small discipline badge appears on each card when "All Disciplines" is selected

### Search

Search works across all disciplines by default. When a discipline is selected, search is scoped to that discipline.

---

## Book Assembly

### Cross-Discipline Books

Users can include chapters from multiple disciplines in a single book:

1. User selects "Mechanical Engineering" in the browser and adds chapters
2. User switches to "Statistics" and adds more chapters
3. The Book Editor shows chapters from both disciplines, with discipline badges

### Dependency Resolution

The auto-include feature (foundational chapter suggestions) works within a discipline. Cross-discipline dependencies are not automatically suggested but can be added manually.

### Book Styling

When a book contains chapters from a single discipline, that discipline's `.sty` file and cover template are used. When a book spans multiple disciplines, the **primary discipline** (the one with the most chapters, or user-selected) determines the styling.

The Book Editor gains a "Primary discipline" selector if chapters from multiple disciplines are present.

---

## Build Pipeline

### Changes to `sync_chapters`

The `sync_chapters` management command is extended to accept a `--discipline` flag:

```bash
python manage.py sync_chapters --discipline mse
python manage.py sync_chapters --discipline mecheng
python manage.py sync_chapters --all   # sync all disciplines
```

Each discipline's Celery Beat schedule syncs its own repo nightly.

### Changes to `build_book`

The build pipeline adds a step to determine and apply discipline-specific resources:

1. Identify the primary discipline from the book's chapters
2. If the discipline has a custom `.sty`, copy it into the workspace (overriding the base)
3. If the discipline has a custom `Frontmatter.tex.template`, use it instead of the default
4. Clone the discipline's repo(s) as needed (chapters may come from multiple repos)

### Multi-Repo Cloning

Currently the build clones a single repo. With multiple disciplines, it clones each discipline's repo as needed:

```python
repos_needed = set(ch.github_repo for ch in book_chapters)
for repo in repos_needed:
    _run(["git", "clone", "--depth=1", f"https://github.com/{repo}.git", ...])
```

This is already partially supported — the `github_repo` field on each chapter identifies which repo to clone.

---

## Admin Panel

### Discipline Management

A new **Disciplines** section in the admin sidebar:

| View | Description |
|---|---|
| Discipline List | Name, slug, repo, chapter count, published toggle |
| Discipline Detail | Edit name, description, repo URL, color, styling, display order |
| Add Discipline | Create a new discipline and trigger initial sync |

### Chapter Management Updates

The chapter list gains a discipline column and filter. The sync button shows which discipline is being synced.

### Dashboard Updates

The dashboard shows chapter and build counts per discipline.

---

## Migration Path

### Phase 1: Discipline model + migration + sync update (~3 days)

1. Create the `Discipline` model with a single entry: "Materials Science and Engineering" (slug: `mse`)
2. Add `discipline` ForeignKey to `Chapter` (nullable, `SET_NULL`)
3. Generate and apply migrations
4. Write a data migration or management command to bulk-assign existing chapters to the MSE discipline
5. Add `discipline` field to the `chapter.json` spec (e.g., `"discipline": "mse"`)
6. Update `sync_chapters` to read the `discipline` field from `chapter.json` and map it to the `Discipline` model by slug
7. Add `Discipline` to Django admin for initial setup
8. Update `ChapterSerializer` to include `discipline` (slug + name) in the API response
9. No frontend UI changes — everything works as before; the discipline field is present but not yet filtered on

### Phase 2: Browse page discipline selector + editor (~4 days)

1. Add discipline tabs/pills to the Chapter Browser header
2. Add discipline filter to the chapters API: `GET /api/chapters/?discipline=mse`
3. Show discipline badge on chapter cards when "All Disciplines" is selected
4. Existing bookmarks and links continue to work (no discipline filter = show all)
5. Store selected discipline in localStorage so it persists across page visits
6. Update chapter count badges to show per-discipline counts
7. Update the Book Editor's left panel chapter catalog to support discipline filtering
8. Update TypeScript `Chapter` interface to include `discipline` field

### Phase 3: Multi-repo sync + admin updates (~3 days)

1. Extend `sync_chapters` to iterate over all published disciplines and sync each repo
2. Add `--discipline` flag to sync a single discipline: `python manage.py sync_chapters --discipline mse`
3. Add Celery Beat schedules per discipline (configurable sync times)
4. Update admin "Sync from GitHub" button to support per-discipline or all-disciplines sync
5. Update admin "Update TOC" and "Update Thumbnails" buttons to work across multiple repos
6. Handle sync errors per-discipline (one failed repo doesn't block others)
7. Ensure GitHub token has access to all discipline repos (document requirement)
8. Test with a second discipline (e.g., a small test set of chapters)

### Phase 4: Discipline-specific styling + build pipeline (~4 days)

1. Support custom `.sty` files per discipline (stored in discipline repo's `Build/template/`)
2. Support custom `Frontmatter.tex.template` per discipline (different cover text, editors, funding)
3. Support custom `matter/` directory per discipline (Postmatter, copyright)
4. Add "Primary discipline" selector to the Book Editor for multi-discipline books
5. Update the build pipeline to:
   a. Determine primary discipline from the book's chapters
   b. Clone each needed discipline's repo
   c. Apply discipline-specific `.sty` (override base style)
   d. Use discipline-specific frontmatter template if available
   e. Fall back gracefully to base OpenChapters style when no custom style exists
6. Apply discipline color theme to the frontend (use `Discipline.color_primary`)

### Phase 5: Admin panel discipline management (~2 days)

1. Add Disciplines section to admin sidebar (list, create, edit, delete)
2. Discipline detail: name, slug, description, repo URL, src path, color, display order, published toggle
3. Chapter list: add discipline column and filter
4. Dashboard: show per-discipline chapter and build counts
5. Audit logging for discipline create/update/delete
6. Superusers only for create/delete; staff can edit details and toggle published

---

## Alternative Approaches Considered

### A. Separate instances per discipline

Run a separate OpenChapters instance for each discipline, each with its own database, frontend, and domain.

**Pros:** Complete isolation; no cross-discipline complexity.
**Cons:** Users need separate accounts; no cross-discipline books; higher operational cost; code duplication.

**Verdict:** Rejected. Too much operational overhead for the benefit.

### B. Discipline as a tag (flat taxonomy)

Add a simple `discipline` CharField to chapters without a separate model.

**Pros:** Simpler implementation.
**Cons:** No place to store discipline-specific configuration (repo URL, styling, color); harder to manage; no admin UI.

**Verdict:** Partially adopted — the `Discipline` model is essentially a structured version of this, with configuration attached.

### C. Hierarchical categories (discipline → subdiscipline → topic)

Support a full category tree: discipline → subdiscipline → topic area.

**Pros:** Fine-grained organization.
**Cons:** Over-engineered for the current scale; most disciplines will have 10–30 chapters; the existing topical/foundational split already provides useful structure within a discipline.

**Verdict:** Deferred. Can be added later if the number of chapters per discipline grows large enough to need it. The `keywords` field on chapters provides informal sub-categorization.

---

## Implementation Phases

```
Phase 1  Discipline model + migration + sync update    ~3 days
Phase 2  Browse page discipline selector + editor      ~4 days
Phase 3  Multi-repo sync + admin updates               ~3 days
Phase 4  Discipline-specific styling + build pipeline   ~4 days
Phase 5  Admin panel discipline management             ~2 days
```

**Total: ~16 days**

Phase 1 is non-breaking and can be deployed immediately. Phases 2–5 can be implemented incrementally as new disciplines are onboarded.

---

## Open Questions — Recommendations

| Question | Recommendation |
|---|---|
| **Who manages new disciplines?** | Superusers only for create/delete; staff can edit details and toggle published. The `published` flag allows staging before going live. |
| **Chapter sharing across disciplines?** | Start with ForeignKey (one discipline per chapter). Shared chapters like "Linear Algebra" can belong to a "Shared/Foundational" discipline visible to all. Upgrade to many-to-many later if needed. |
| **Domain structure?** | URL paths (`/chapters?discipline=mse`) — simpler, single deployment, no DNS/SSL per discipline. |
| **Build queue isolation?** | Not needed initially. Add priority-based task routing later if one discipline dominates the queue. |
| **GitHub token scope?** | A single classic PAT with read access to all discipline repos is simplest. Document that the token must have access to all repos listed in `Discipline.github_repo`. |
