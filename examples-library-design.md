# Worked-Examples Library — Design & Implementation Plan

Detailed design for `todo.txt` item #5. Reframes the original "problem sets"
brief as a **worked-examples library**: every entry has a public solution,
and instructors who want a problem-only handout get it via a per-build
flag.

## Decisions locked in

| Question | Decision |
|---|---|
| Pedagogical framing | Worked examples (solution always public). Solution-hiding gating is unenforceable on a fully open site. |
| Placement in built book | Append an "Examples" section to each chapter at build time. |
| Solutions in builds | Per-build flag (`include_examples` × `include_solutions`) — three useful states: full worked examples / problems-only practice / clean main text. |
| Moderation | Admin review queue. `draft → pending → published / rejected`. |
| Authoring UX | Two LaTeX textareas + tag picker + **server-side compile preview button** (PDF round-trip via the existing build worker). |
| Discovery | Public `/examples` browse page **and** examples surfaced on each chapter detail page. |
| Preview rebuild trigger | Explicit "Preview" click in the form. No auto-rebuild on PATCH. Authors are responsible for re-previewing after edits; submit blocks if `preview_built_at < updated_at`. |

---

## 1. Data model

New app section in `catalog/` (no new Django app — `Example` lives next to `Chapter`).

### `Example`

| Field | Type | Notes |
|---|---|---|
| `id` | auto PK | |
| `author` | FK → User | `on_delete=PROTECT`. |
| `chapters` | M2M → Chapter | At least one tag required (validate in serializer). |
| `primary_chapter` | FK → Chapter | One of `chapters`. Determines the LaTeX preamble used for snippet compile. Defaults to first M2M selection. |
| `statement_tex` | TextField | LaTeX source. Required. |
| `solution_tex` | TextField | LaTeX source. Required (worked-example invariant). |
| `difficulty` | CharField(16) choices | `INTRODUCTORY` / `STANDARD` / `ADVANCED`. Used as filter. |
| `license` | CharField(64) | Default `CC BY-NC-SA 4.0`. Future-proofing only; one value for now. |
| `status` | CharField(16) choices | `DRAFT` / `PENDING` / `PUBLISHED` / `REJECTED`. |
| `rejection_reason` | TextField, blank | Admin fills in when rejecting; surfaced to author. |
| `preview_built_at` | DateTimeField, null | Set when preview PDF compile succeeds. |
| `preview_build_log` | TextField, blank | Last 8 KB of arara output for diagnosis. |
| `created_at`, `updated_at` | auto | |

**Snippet artifacts.** Cached PDF lives at `media/examples/<id>.pdf`,
parallel to `media/pdf_labels/`. Worker writes; web reads. Production
needs a `media_examples` named volume mounted on both services
(precedent: `media_pdf_labels`).

**Indexing.** `status`, `(status, primary_chapter)`, and the M2M
through table are the only filter shapes. No FTS in v1 — chapter and
difficulty filters are sufficient.

### `BookBuildOptions` extension

Two new BooleanFields on the existing `Book` (or `BookBuild`, whichever
holds per-build options today):

- `include_examples` (default `True`)
- `include_solutions` (default `True`, ignored when `include_examples=False`)

Plumbed into the build context, consumed by the book Jinja template.

### Migrations

- `catalog/migrations/00XX_example.py` — creates `Example` + M2M.
- `books/migrations/00XX_build_options.py` — adds the two flags.

Both reversible. No data backfill (everything starts empty).

---

## 2. API surface

All routes under `/api/examples/`.

### Public (AllowAny)

| Method | Path | Returns |
|---|---|---|
| GET | `/api/examples/` | List of `published` examples. Filters: `?chapter=<chabbr>`, `?difficulty=`, `?search=`. Paginated. |
| GET | `/api/examples/<id>/` | Detail: statement, solution, tags, difficulty, author display name. |
| GET | `/api/examples/<id>/preview.pdf` | Cached preview PDF. 404 if not built. Same `FileResponse` pattern as `ChapterPdfLabelsView`. |

Listing serializer omits `solution_tex` to keep payloads small —
solutions only appear in the detail endpoint and the preview PDF.

### Authenticated (author scope)

| Method | Path | Behavior |
|---|---|---|
| POST | `/api/examples/` | Create as `DRAFT`. |
| PATCH | `/api/examples/<id>/` | Update — only own examples in `DRAFT` or `REJECTED`. |
| DELETE | `/api/examples/<id>/` | Delete — only own `DRAFT`. |
| POST | `/api/examples/<id>/preview/` | Trigger preview compile. Returns Celery task ID. Author can call any time on own examples. |
| POST | `/api/examples/<id>/submit/` | `DRAFT` or `REJECTED` → `PENDING`. Requires `preview_built_at >= updated_at` (preview must be fresh, since previews aren't auto-rebuilt on edit). |
| GET | `/api/examples/mine/` | Author's own examples across all statuses. |

### Admin (IsAdminUser)

| Method | Path | Behavior |
|---|---|---|
| GET | `/api/admin/examples/?status=pending` | Review queue. |
| POST | `/api/admin/examples/<id>/approve/` | `PENDING` → `PUBLISHED`. |
| POST | `/api/admin/examples/<id>/reject/` | `PENDING` → `REJECTED` with `rejection_reason`. |

No bulk-approve in v1.

---

## 3. Build pipeline

### 3a. Snippet preview (per-example)

New management command `catalog/management/commands/build_example_preview.py`,
modeled on `build_chapter_pdf_labels.py`. Sequence:

1. Fetch `Example` by id.
2. Resolve preamble: clone `primary_chapter`'s repo at HEAD, copy its
   `preamble.tex` and any chapter-private style files into the workspace.
3. Render a minimal Jinja template
   `Build/scripts/main_example.tex.j2`:
   - `\documentclass{openchapters}` (or whichever class the chapters use)
   - `\input{preamble.tex}`
   - `\begin{document}`
   - `\section*{Example}` → `{{ statement_tex }}`
   - `\section*{Solution}` → `{{ solution_tex }}`
   - `\end{document}`
4. Run arara via existing worker invocation.
5. On success: atomic `os.replace` to `media/examples/<id>.pdf`,
   set `preview_built_at`, clear `preview_build_log`.
6. On failure: leave artifact untouched, write last ~8 KB of stderr to
   `preview_build_log` for the author/admin to debug.

Time limits: `time_limit=120`, `soft_time_limit=90`. Tighter than
chapter builds — examples are short.

Celery wrapper `build_example_preview_task(example_id)` invokes the
command. Triggered by:
- Author clicking "Preview" in the form (sync API → enqueue task → poll).
- Author calling submit (auto-rebuild if `preview_built_at` is null or
  `updated_at > preview_built_at`).

### 3b. Book build integration

At book build time, for each chapter in the assembled book, query
published examples where `chapter` is in the M2M. Pass them through to
the book Jinja template under a per-chapter key. Cross-chapter
examples (tagged to multiple chapters in the same book) render once
under the **earliest-ordered chapter** in that book to avoid
duplication.

Template change in the book entry point (`Build/scripts/main.tex.j2`
or whichever assembles chapters):

```latex
{% for ch in chapters %}
  \input{{ ch.body_tex }}
  {% if include_examples and ch.examples %}
    \section*{Worked Examples}
    {% for ex in ch.examples %}
      \subsection*{Example {{ loop.index }} — {{ ex.difficulty }}}
      {{ ex.statement_tex }}
      {% if include_solutions %}
        \paragraph{Solution.}
        {{ ex.solution_tex }}
      {% endif %}
    {% endfor %}
  {% endif %}
{% endfor %}
```

If `include_examples=True` and `include_solutions=False`, the section
becomes a problem-only practice handout — same UI, different artifact.

### 3c. Cached preview reuse

The book build does **not** invoke the snippet compile pipeline — it
inlines the LaTeX directly. The cached `media/examples/<id>.pdf` is
only for previewing, not for build inclusion. (Inlining keeps page
breaks and numbering coherent across the chapter.)

---

## 4. Frontend

### Public pages (no auth)

**`/examples`** — new public route.
- Filters: chapter dropdown (populated from chapters API), difficulty
  pills, search box.
- Card list: statement first ~200 chars (KaTeX-rendered for math
  fidelity), difficulty badge, chapter chips.
- Each card links to `/examples/<id>`.
- "Submit an example" CTA → `/examples/new` (or `/login` redirect).

**`/examples/<id>`** — detail.
- Statement and solution rendered with KaTeX (best-effort, may fall
  short for custom macros).
- "Open preview PDF" button → `/api/examples/<id>/preview.pdf` (full
  fidelity).
- Chapter tags link back to chapter detail pages.

**Chapter detail page** (existing).
- New "Examples" section after the chapter description, listing
  tagged published examples as compact cards. Surfaces the corpus to
  readers who arrived via a chapter rather than the catalog.

### Authenticated pages

**`/examples/new`** — submission form.
- Statement textarea, solution textarea (plain `<textarea>` with
  monospace font in v1; CodeMirror upgrade deferred to phase 4 — no
  editor library is currently in the frontend bundle, so adding one
  costs ~150–200 KB gzipped that every public-page visitor would
  pay).
- Chapter multi-select (use existing chapter list API).
- Primary chapter dropdown (constrained to selected chapters).
- Difficulty radio (3 options).
- Buttons: **Save draft** | **Preview** | **Submit for review**.
- "Preview" calls `/preview/`, polls task, embeds returned PDF in an
  `<iframe>` below the form.
- "Submit" disabled until preview has compiled successfully.

**`/examples/<id>/edit`** — same form, prefilled. Shown for own
examples in `DRAFT` or `REJECTED` (with `rejection_reason` displayed
prominently).

**`/profile`** (existing) — new "My Examples" section listing user's
drafts/pending/published/rejected with status badges.

### Admin pages

**`/admin/examples`** — review queue.
- List of `PENDING` examples with submit time, author, primary
  chapter, "Open preview" link.
- Inline approve / reject (with reason textarea) buttons.

### Book builder

The existing book builder gets two new checkboxes near the build
trigger:

- ☑ Include worked examples
- ☑ Include solutions  *(greyed out when above is unchecked)*

Below the checkboxes, a small summary: "*N examples will be included
across these chapters.*" — counted from the public list API filtered
by the chapters in the current book.

---

## 5. Phasing & deliverables

Each phase ships independently and is committable as one PR. Total
estimated effort: **6–8 dev-days** end to end.

### Phase 1 — Foundation *(~2 days)*

Goal: examples can be submitted, listed publicly, and tagged to
chapters. **No preview, no build integration yet.**

- `Example` model + migration.
- Serializers (list / detail / write).
- Public list/detail views.
- Authenticated CRUD for own drafts.
- Admin queue + approve/reject endpoints.
- Frontend: `/examples` browse, `/examples/<id>` detail, `/examples/new`
  form (without preview), chapter detail page surfaces tagged
  examples, `/admin/examples` queue.

**Done when:** an admin user can seed three examples through the API,
they appear publicly, and the chapter detail page lists them.

### Phase 2 — Snippet preview *(~1.5 days)*

Goal: authors can compile their LaTeX before submitting; admins
review against the rendered PDF.

- `Build/scripts/main_example.tex.j2`.
- `build_example_preview` management command.
- `build_example_preview_task` Celery task.
- `POST /preview/` endpoint, `preview.pdf` endpoint.
- `media_examples` named volume in `docker-compose.prod.yml`.
- Pre-create `/app/media/examples` in both Dockerfiles (precedent:
  `media/pdf_labels` fix in commit `dd7d0e1`).
- Frontend: "Preview" button on the form, embed iframe, poll task.
- Admin queue shows preview link.
- Submit endpoint requires `preview_built_at` to be fresh.

**Done when:** an author can paste LaTeX, click Preview, see the PDF,
fix issues, and submit.

### Phase 3 — Book build integration *(~1.5 days)*

Goal: examples flow into typeset books.

- `BookBuildOptions` migration (two flags).
- Book builder UI: two checkboxes + example-count summary.
- Book entry-point Jinja template: append-examples loop.
- Cross-chapter dedup: render under earliest in-book chapter.

**Done when:** a book containing two chapters, each with one tagged
example, builds three artifacts on demand: full / problems-only /
no-examples — by toggling the two checkboxes.

### Phase 4 — Polish *(~1 day, opportunistic)*

- KaTeX in-browser math rendering on `/examples/<id>` (best-effort).
- "Examples count" column on the public chapter catalog table.
- "My Examples" section on profile page.
- CodeMirror LaTeX mode for the textareas (`@uiw/react-codemirror` +
  `@codemirror/lang-stex`). Only worth doing if real authors ask for
  it; the Preview button + `preview_build_log` already catch broken
  LaTeX.

### Deferred to later iterations

- Topic tagging (free-form tags beyond chapter associations).
- Versioning of examples (edits to a published example currently
  silently update — fine for v1).
- Variants ("same problem, different numbers").
- Per-problem build artifacts cached in DB (we already cache the
  preview PDF on disk).
- FTS over example text.
- Bulk admin actions.

---

## 6. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Hostile / broken LaTeX bricks the worker. | Tight `time_limit=120` on the preview task; arara already runs in a constrained worker container; never compile during book build (we inline already-compiled-clean snippets). |
| An example uses a macro available only in chapter A's preamble, but is tagged to chapter B too. | `primary_chapter` selects which preamble drives the snippet compile. Authors can include the example under multiple chapters only after verifying the preview against the primary. |
| A previously approved example becomes broken after a chapter preamble change. | Nightly task re-builds previews for `PUBLISHED` examples; failures flip status to `REJECTED` with an auto-reason and email the author. *Defer to phase 4.* |
| Cross-chapter examples in a partial book duplicate or vanish. | "Render once under earliest in-book chapter" rule (deterministic and stable across rebuilds). |
| Solution-hiding workaround attempts (instructors emailing me to gate solutions). | Documented decision: this is a worked-examples library. Instructors who need un-spoiled problems can build with `include_solutions=False`. |
| Submission spam. | Admin queue is the gate. Add rate limiting only if it becomes a real problem. |
| Author edits a `PUBLISHED` example. | v1: edit is allowed only on `DRAFT`/`REJECTED`. Edits to published require admin to revert to `DRAFT` first. Keeps the corpus stable. |

---

## 7. Out of scope for this plan

- Migration of any existing problem sets (none exist).
- Search ranking / FTS over examples.
- Per-user "favorite" or "tried" tracking.
- Comments / discussion on examples.
- Export of examples to standalone PDFs outside of book builds.
- Production deployment commands per phase — follows the standard
  flow already documented in `docs/deployment-guide.md`.

---

## 8. Open questions to revisit before phase 1

1. **Chapter-author auto-publish escape hatch** — deferred. Worth
   revisiting only if admin-queue throughput becomes a bottleneck.
