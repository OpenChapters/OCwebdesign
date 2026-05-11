# OpenChapters — A Critical Look (May 2026)

A candid review of OCwebdesign as it stands today. This is meant to be
additive to `docs/PROJECT_EVALUATION.md` (March 2026), which already
catalogues the historical security/reliability fixes; the focus here
is on what's surfaced *since* (worked-examples library, batch import,
version ledger, per-build example picker, post-publish edits, backups),
on cross-cutting concerns the earlier doc skips, and on the user
experience — which the earlier doc only touched in passing.

I've tried to be specific. Where I name a file/line, the criticism is
actionable; where I gesture at a pattern, the goal is to flag it for a
later, dedicated audit.

---

## 1. What's genuinely good

These aren't platitudes. Most of these are decisions that an inexperienced
project gets wrong, and this one didn't:

- **Clean app boundaries.** `catalog`, `books`, `users`, `admin_api` carve
  responsibilities along the right seams. Cross-app imports are scarce
  and one-directional (books depends on catalog, not vice versa). Adding
  the worked-examples subsystem inside `catalog` was the right call; it
  reuses the chapter taxonomy without creating a fifth app.

- **The build pipeline isn't naive.** `_validate_build_data` in
  `books/tasks.py` regex-validates repo names and paths *before* every
  `subprocess.run`. Failed builds archive `main.log`, `main.tex`, and
  `build.log` to `media/pdfs/failed_builds/` (last 10 kept). A 25-minute
  soft timeout is wired up. Most LaTeX-as-a-service hobby projects fall
  over on the second of these three; this one has all three.

- **Auditing infrastructure is layered.** `AuditEntry` records admin
  actions with IP/user/target. The newer `ExampleVersion` model captures
  pre-save snapshots of edited examples via a Django signal with
  thread-local user attribution — a tasteful pattern that avoids polluting
  every view with explicit "audit_log()" calls. (See §3.7 on the missing
  UI for this.)

- **Signed download tokens with user binding.** `book_id:user_id` payload
  means a leaked email link can only be redeemed by the original recipient,
  and an admin can see in logs which user actually downloaded. Bounded
  blast radius is the right design.

- **Worked-examples lifecycle is well thought-through.** Draft → pending →
  published → rejected, post-publish re-review on edit, per-author slug for
  idempotent batch re-imports, KaTeX best-effort with an amber fallback
  for the source, signed preview-PDF token with TTL. The shape of the
  feature respects authors, reviewers, and the LaTeX-only reality.

- **Per-build example picker stores deselections only.** The default
  ("include everything currently published") survives catalog churn, new
  approvals auto-included, deletions silently tolerated. This is the right
  failure mode — easy to get wrong, easy to over-engineer.

- **Backups are real, not aspirational.** `scripts/backup.sh` runs nightly
  via cron, takes a `pg_dump` and tars the media volumes, prunes by age.
  Most projects this size only document this; it's actually wired up here,
  with retention.

- **Documentation depth.** `docs/user-guide.md` (532 lines),
  `docs/api-reference.md` (1339), `docs/deployment-guide.md` (1093),
  `docs/admin-guide.md` (449). Most one-developer projects have a sad
  README and nothing else. This isn't that.

- **Pragmatic React Query + minimal context.** Server state lives in
  TanStack Query; only AuthContext and ToastProvider are global. No
  Redux/Zustand, no premature abstraction. This is the right default
  for a 30-route SPA.

- **The reviewer remembered Safari.** Cover image proxy + local cache
  fixed a real concurrent-connection problem; ETag-aware serving is
  in place. Small detail, big quality signal.

---

## 2. Behind the scenes — what could be improved

### 2.1 `build_book` is doing too much

`books/tasks.py` is **1119 lines**, and `build_book` is the centerpiece.
It clones repos, merges bibliographies, copies figures, runs arara,
parses logs, handles soft-timeout, emails the user, and writes a BuildJob
row on the way out. There is **one** BuildJob update on completion — no
per-stage status, no progress %, no per-stage timing.

Consequences:

- The user stares at "Building…" for 1–3 minutes with no idea whether
  the job is at "cloning repos" or "running pdflatex pass 3 of 3."
- Retry granularity is all-or-nothing. A flaky GitHub fetch forces a
  full re-typeset.
- Unit testability is poor. `tests/test_build_pipeline.py` covers the
  *validation* helpers and serialization; the actual orchestration is
  too tangled to test cleanly.

A staged design — `BuildStep(book, name, started_at, finished_at, log)`,
populated by helper functions each Celery worker calls in sequence — would
unlock progress UI, retries, and tests in one move. This is the biggest
"latent debt that costs you on every new feature" item in the project.

### 2.2 Test coverage hasn't kept up with features

88 tests is a good baseline (and a much better story than most projects
have at this size). But the test directory hasn't grown with the
worked-examples subsystem:

| Subsystem | Test coverage status |
|---|---|
| Auth, signing, basic book CRUD | Good (existing tests) |
| Build pipeline validators | Good |
| Worked-example create/edit/lifecycle | **None visible** |
| Batch import (parser + commit) | **None** |
| ExampleVersion signal | **None** |
| Example picker / `excluded_example_ids` | **None** |
| Post-publish edit re-review flow | **None** |

Every one of these last five has surfaced a bug or incident in the past
month — silent 500s, STORAGES regression, circular publication workflow,
worker-not-reloaded. A handful of integration tests (factory + APIClient,
exercising the view → serializer → model path) would have caught at least
three of these before they shipped. The `factories.py` already exists; the
infrastructure cost is near zero.

There's no visible CI config. `.coverage` is committed but no GitHub
Actions / workflow file runs `pytest`. Tests only protect you if they
run, and they currently only run when you remember.

### 2.3 Observability is thin

- **Logging is configured but unstructured.** The recent prod incident
  with silent 500s (the `LOGGING` default filter that requires
  `DEBUG=True` to surface to console) cost a debugging session and was
  fixed with a hand-rolled config in `ocweb/settings/base.py`. No request
  IDs are attached to log lines; correlating a user-reported failure with
  a worker traceback is grep-and-pray.
- **`BuildJob.log_output` is a single blob.** No per-step boundaries.
- **No metrics.** No Prometheus, no flower, no per-task timing exported.
  PROJECT_EVALUATION lists this as longer-term; in practice every new
  feature you add without it costs more to debug than it would cost to
  add. Even a basic `/api/metrics/` exposing build durations and queue
  depth would help.
- **Sentry/error-tracking is absent.** Five-figure-user platforms have
  this; a hundred-user platform is the perfect time to add it because
  the noise floor is low and every signal is real.

### 2.4 TypeScript and frontend linting are both off

`tsconfig.json` has `strict: false`. No eslint or prettier config in the
repo. For a 30-route SPA with a 749-line `BookEditorPage.tsx`, both of
these decisions actively cost you:

- The `is_own ?? (status !== 'published')` fallback we added recently is
  exactly the kind of nullable-vs-undefined gotcha strict null checking
  catches at compile time instead of producing a runtime quirk.
- No lint means inconsistent imports, unused variables, hooks-rule
  violations, and stale code don't fail anywhere.

Enabling strict mode incrementally (file-by-file `// @ts-strict` or a
`tsconfig.strict.json` only for new files) and adding `eslint --max-warnings 0`
to the build are both ~one-afternoon investments.

### 2.5 API shape is mixed and there's no schema

`books/views.py` uses a hybrid of `generics.RetrieveUpdateDestroyAPIView`
(for Book CRUD) and bespoke `APIView` subclasses for everything else
(BuildTrigger, Reorder, ExamplesAvailable, Cover, Library). There's no
single convention: some views accept JSON bodies, some accept query
params, some return `{detail: ...}` on error, some return DRF field
errors. Working with the API from outside (curl, an admin script, an
eventual mobile client) requires reading source.

`drf-spectacular` is listed as deferred in PROJECT_EVALUATION; in the
meantime, `docs/api-reference.md` (1339 lines) is hand-maintained, which
guarantees it will drift. The new `GET /api/books/<id>/examples-available/`
endpoint we shipped today is not yet in `api-reference.md`. This will
keep happening.

### 2.6 Settings layout has rough edges

`ocweb/settings/base.py` reads ~20 env vars at module load with
`django-environ`. A missing var produces a generic `ImproperlyConfigured`
on startup, not a friendly "you forgot `SECRET_KEY`" message. Two
recent prod incidents (`STORAGES` missing `default`, `LOGGING` silent
500s) were both settings-shape issues with no compile-time guard.

`GIT_PROVIDER` logic is split between `base.py` and
`catalog/git_provider.py`; `HTML_BUILD_ENABLED` is checked in multiple
places. A `settings/runtime.py` that consolidates feature flags into one
namespace, plus a startup sanity check (similar to the
Turnstile-test-key warning that already exists), would have caught the
last two prod regressions.

### 2.7 Models and small data-modeling debts

- **`ExampleVersion` has no UI.** The model captures snapshots, the
  signal fires correctly, but no admin view and no author view reads
  them. Right now the table only accumulates rows nobody sees. Either
  expose it (an admin "view history" link on the example queue, an
  author "see my revisions" tab in their profile) or remove the model —
  carrying unused infrastructure is worse than carrying nothing.
- **`Example.slug` is half-exposed.** Used by batch import for
  idempotent upserts, not by the regular editor. Two creation paths
  with different identity semantics. Either expose slug in the editor
  (advanced field, optional) or document why it only matters for
  batch imports.
- **`BuildJob.log_output: TextField`** can grow large (full arara
  stdout for a 30-chapter build is megabytes). No truncation, no
  archive-to-disk pattern for the success path. Eventually this
  bloats Postgres.
- **`Book.parts` queries are nested-serializer-everything.**
  `BookSerializer` returns parts → book_chapters → chapter_detail in
  one shot. Fine at current scale, but `examples_count` is computed
  per-book per-list-call without queryset annotation; the book list
  page will N+1 once there are 50+ books.

### 2.8 Frontend bundle versioning

We had a "Cmd+Shift+R fixed it; the Batch Import button now shows up"
incident this session. Vite 6 produces hash-named bundles by default,
but the SPA shell (`index.html`) is what nginx serves and is the cache
weak point. If `Cache-Control` on `index.html` isn't `no-cache` (or
short max-age), every release risks giving returning users stale UI
until a hard reload. Worth confirming the nginx config sets this
correctly.

### 2.9 Celery queue separation

Build jobs (1–3 minutes, occasionally 25), email deliveries (seconds),
HTML-rebuild auto-chains, and the nightly `sync_chapters` Beat job all
share one queue with 4 workers. A 25-minute build can hold up email
retries on a different book. Splitting into `builds` and `default`
queues with separate worker pools is a 30-line change with material
reliability upside.

### 2.10 Multi-stage docker / no staging environment

Build images are rebuilt on prod from the same Dockerfile that runs
locally. A staging container (same compose, separate domain) would
catch the kind of "STORAGES has different shape in prod" regression
without exposing real users to it. Not urgent at current traffic;
worth scheduling before any user-facing milestone.

---

## 3. User experience — what could be improved

### 3.1 Mobile is unusable on 20 of 21 pages

The only page with responsive Tailwind classes (`sm:`/`md:`/`lg:`) is
`ChapterBrowserPage.tsx`. Every other page — including the user guide
itself, `MyBooksPage`, `ExamplesPage`, and the public chapter detail
page — uses `max-w-6xl px-6` with no mobile overrides. On a phone:

- Tables and modals overflow horizontally.
- The Book Editor is unusable (two-pane layout collapses).
- The hover-to-show-TOC on chapter cards doesn't work on touchscreens
  (no tap-to-show fallback).

Academic users read on phones all the time. PROJECT_EVALUATION lists
"Mobile-responsive Book Editor" as low-priority; in practice the entire
public-facing surface is the priority. A first pass — collapsing the
Book Editor's two panes into tabs on `< md`, replacing hover with tap,
adding `flex-wrap` everywhere a fixed pixel width appears — is a
week of focused work that doubles the addressable audience.

### 3.2 Accessibility is essentially absent

The frontend audit found:

- Zero `aria-*` attributes across all pages.
- Forms in public pages without associated `<label>` elements.
- Modals (`ExampleSelectionModal`, the new cover upload prompt,
  delete-account confirmations) lack `role="dialog" aria-modal="true"`,
  no focus trap, no Escape-to-close.
- No skip-to-content link.
- Drag-and-drop is keyboard-accessible (dnd-kit ships this) — the rest
  is mouse-only.

For an academic platform, this isn't a "nice to have." Universities
have policy requirements (Section 508 in the US, WCAG 2.1 AA in many
EU institutions). If OpenChapters wants institutional adoption, this
gap will block it.

A 1-week a11y pass: add labels to all form inputs, wrap modals in a
focus-trap library (`focus-trap-react` is one line), add ARIA roles to
the navbar and main content, run `axe-core` once and fix the top 20
findings. None of this is exotic.

### 3.3 No dark mode

`tailwind.config.js` doesn't enable `darkMode`. Every page is light
blue/white. Open-source documentation users have strong dark-mode
preferences, and "I read everything on the platform at night" is a
real user. PROJECT_EVALUATION ranks this low; I'd argue medium because
the implementation cost is small (`darkMode: 'class'` + a toggle in
the navbar + ~50 utility class swaps) and the visibility is high.

### 3.4 Build progress is opaque

A user clicks "Build PDF + HTML" and sees "PDF + HTML build queued — the
HTML pass will take several minutes." For the next 3–10 minutes there is
no further information. The status badge cycles "Queued → Building →
Complete." A user who has hit "Build" and is unsure whether the
typesetting started in the first 30 seconds has no way to confirm.

`BuildJob` doesn't carry per-step status today. Adding a step model
(see §2.1) lights up a real-time progress strip: "Cloning 12 chapter
repos (4/12)…" → "Running pdflatex (pass 2 of 3)…" → "Embedding
figures…" → "Rendering MathJax (lwarp pass)…". For a build that takes
3 minutes, this transforms perceived speed and trust.

### 3.5 Toast errors auto-dismiss in 4 seconds

`Toast.tsx` dismisses everything after 4000ms. For an info toast ("Build
queued") that's fine. For an *error* toast ("Build failed. Check the
build status page for details.") it's not — by the time the user has
read it and oriented to where the link is, it's gone. Two changes:

- Errors should be sticky (no auto-dismiss; require explicit close).
- Errors with a follow-up action should embed the link in the toast,
  not gesture at "the status page."

### 3.6 The example picker is hidden

We added "Customize examples…" as a small underlined link next to a
checkbox. A user who hasn't read the changelog won't find it. Two
mitigations:

- When the user has excluded examples, show "**3 of 12** examples
  included" prominently next to the toggle, with the link relabeled
  "change…" — turns the link from a feature surface into a *state*
  surface.
- The first time a user with `examples_count > 0` opens the editor,
  show a one-time inline tooltip ("You can choose which examples to
  include — click 'Customize examples…'").

### 3.7 ExampleVersion has no surface (UX side)

Same point as §2.7, but from the user side: an author who corrected an
example three months ago and wonders "what did I change" has no
recourse. An admin who sees a pending example with `version_no > 1`
has no way to see what differed. The data exists; the UI doesn't.

A minimal version: on the example detail page (author view), a
"Revision history" expander showing dates and a per-field diff. On the
admin queue, the same expander showing prior published version vs.
current pending version. Two days of work.

### 3.8 "My Books" has no sort/filter/search

The list orders by `-created_at` and that's it. With 30+ books over a
semester (a realistic count for a course author), finding a specific
book is scroll-and-scan. Adding a search input and a status filter
(complete / draft / failed) is a small change with big quality-of-life
returns.

### 3.9 No "preview first chapter" for a book

Worked examples can be previewed (snippet typesetting). Books can't —
the user commits to a full build (1–3 minutes), waits, sees the result.
For a user iterating on book structure (adding a chapter, checking that
the TOC looks right), this is the slowest possible loop.

A "preview structure" build (TOC only, no body content) would take
seconds and answer "is this book shaped correctly?" without burning a
full build slot. Reusing the existing pipeline with a flag that emits
only `\maketitle` + `\tableofcontents` + `\input`-of-empty-chapters
gets you there.

### 3.10 Auth refresh, password reset, and account deletion polish

- Account deletion confirms twice but has no cooling-off period. A
  small "deletion will complete in 24 hours; sign in again to cancel"
  banner with a row on the dashboard would prevent a class of
  customer-support requests.
- Password reset emails work, but the reset page after success
  redirects to login without surfacing "your password has been reset
  — sign in with your new password." Small wording, big clarity.

### 3.11 Search has prefix-match defaulting; nobody knows

Typing `sym` matches `symbol`, `symmetry`, `symmetric`. This is great
behavior, badly hidden. A one-line hint under the search input
("Searches by word prefix — `sym` finds `symbol`, `symmetry`…") sets
expectations. The same hint should mention quotes for phrases.

### 3.12 The chapter "Read Online" experience

Per-chapter HTML is built independently. Cross-references to other
chapters render as italicized label strings (`NUMSYS:sec:quaternions`),
not as links. The user guide acknowledges this, but in the reader UI
itself there's no acknowledgment — a user sees italic text and
assumes it's broken. A small `<sup>(other chapter)</sup>` indicator
on these references, or a tooltip on hover, would explain the
limitation in-context.

### 3.13 Author-side feedback loop on rejected examples

When an admin rejects an example, the author sees the rejection reason
at the top of the editor. Good. But there's no notification: the
author has to find the example to discover it was rejected. Either an
email on rejection (template + Celery task; the infrastructure is
already there) or an in-app notification badge on the navbar would
close the loop.

### 3.14 The author batch-import gate is invisible

`SiteSetting.author_batch_import_enabled` defaults False. The user
guide documents the feature unconditionally — a non-admin reader who
follows the guide will not find the button. Either default it on, or
gate the documentation section behind the same setting (the user
guide endpoint already serves dynamic content; it could read the
flag and conditionally include the section).

---

## 4. Recommended priorities

Ranked by ratio of impact to effort. Numbers are rough effort buckets
(days of focused work). ✅ marks items shipped to production during
the May 2026 push.

| # | Item | Effort | Impact | Status |
|---|---|---|---|---|
| 1 | CI workflow runs pytest on every push | 0.5 | Prevents future regressions | ✅ |
| 2 | Integration tests for example lifecycle + batch import + picker | 2 | Closes the §2.2 gap directly | ✅ |
| 3 | Strict-mode TypeScript on new files + eslint | 1 | Catches a class of runtime bugs | ✅ |
| 4 | Mobile responsive pass on Browse / Examples / Detail / User Guide | 5 | Doubles usable surface | ✅ |
| 5 | A11y pass — labels, ARIA, focus traps, axe-core audit | 5 | Unblocks institutional use | ✅ |
| 6 | Per-step BuildJob (model + worker emit + UI strip) | 4 | Makes builds feel fast; enables retry granularity; unlocks unit tests | ✅ |
| 7 | Sentry or equivalent error tracking | 0.5 | Catches the next silent 500 in seconds | ✅ |
| 8 | Toast: sticky errors with action links | 0.5 | Stops losing error messages | ✅ |
| 9 | ExampleVersion UI (author + admin) | 2 | Realizes the ledger investment | ✅ |
| 10 | drf-spectacular + auto-generated OpenAPI | 1 | Eliminates doc drift |  |
| 11 | Dark mode | 2 | High visibility, low cost |  |
| 12 | "Preview structure" book build | 2 | Big iteration-speed win for authors |  |
| 13 | Celery queue separation (builds vs default) | 0.5 | Email retries no longer blocked by long builds | ✅ |
| 14 | Staging environment | 1 | Catches the next STORAGES-shaped regression |  |
| 15 | Cooling-off period on account deletion | 0.5 | Recovers from accidental clicks | ✅ |

Bonus shipped alongside item 6: the build pipeline now retries
transient `git clone` failures (GitHub 5xx) and keeps a per-repo
warm-clone cache so subsequent builds skip re-cloning from GitHub.

If I were budgeting one focused month, I'd pick items 1, 2, 4, 5, 6
(CI + tests + mobile + a11y + per-step build progress). That single
month upgrades the project from "works for technical authors at a
small scale" to "credible for institutional adoption" without changing
the feature surface at all.

---

## 5. A note on the project's posture

A lot of what's good here — auditing, signed tokens, real backups,
deep docs, a thoughtful examples lifecycle — points to a developer
who has been bitten before and remembers. That's the foundation a
small open-source platform needs.

The gaps cluster in two categories: (a) the cost of moving fast on
features without commensurate investment in tests, CI, and
observability (the silent-500 and worker-not-reloaded incidents this
month are early warnings), and (b) the cost of building entirely
desktop-first without an a11y or mobile pass (which becomes a hard
ceiling on adoption rather than a soft one). Both are addressable
with sustained effort over a month; neither is a redesign.

If the goal is "platform that materials-science authors use" then
the current trajectory is fine. If the goal is "platform that
universities adopt as an OER channel," items 4 and 5 in §4 stop
being optional.
