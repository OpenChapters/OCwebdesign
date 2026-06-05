"""
Celery tasks for the books app.

build_book      — full LaTeX build pipeline for a user's book assembly (PDF)
build_book_html — per-book HTML build via lwarp
deliver_pdf     — email the completed PDF link to the user (via SMTP)
deliver_book_html — email the HTML "view online" + zip download link
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-step build progress
# ---------------------------------------------------------------------------

def _reset_steps(build_job) -> None:
    """Drop any leftover steps from a previous run on this job. Each
    build_book / build_book_html invocation re-populates the list from
    scratch."""
    from books.models import BuildStep
    BuildStep.objects.filter(build_job=build_job).delete()


def _set_step_detail(step, detail: str) -> None:
    """Update the live "current sub-message" on a running step. Cheap —
    issues a single column UPDATE."""
    step.detail = detail[:500]
    step.save(update_fields=["detail"])


@contextmanager
def _build_step(build_job, *, name: str, label: str, order: int, log_lines: list[str]):
    """Wrap a stage of the pipeline so its lifecycle (start/finish/fail)
    is recorded as a BuildStep row.

    Use as:
        with _build_step(job, name="clone", label="Cloning sources",
                         order=1, log_lines=log_lines) as step:
            ...
            _set_step_detail(step, f"{i} of {n}")
            ...

    On success the step is marked SUCCEEDED at exit. On exception the
    step is marked FAILED with the exception summary and the tail of
    the build log captured for the status page — then re-raised so the
    outer except in build_book still records the job-level failure.
    """
    from books.models import BuildStep
    step = BuildStep.objects.create(
        build_job=build_job,
        name=name,
        label=label,
        order=order,
        status=BuildStep.Status.RUNNING,
        started_at=timezone.now(),
    )
    try:
        yield step
    except Exception as exc:
        step.status = BuildStep.Status.FAILED
        step.finished_at = timezone.now()
        step.detail = f"{type(exc).__name__}: {exc}"[:500]
        step.log_tail = "\n".join(log_lines[-80:])[:8000]
        step.save()
        raise
    else:
        # Caller may have already populated detail via _set_step_detail;
        # only set the closing status here.
        step.status = BuildStep.Status.SUCCEEDED
        step.finished_at = timezone.now()
        step.save(update_fields=["status", "finished_at"])

# Patterns for validating chapter metadata used in subprocess calls.
_SAFE_REPO = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
_SAFE_PATH = re.compile(r"^[a-zA-Z0-9_/.+-]+$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_build_data(request_data: dict) -> None:
    """
    Validate all paths and repo names in build_request.json before any
    subprocess calls. Raises ValueError on invalid data.
    """
    for part in request_data.get("parts", []):
        for ch in part.get("chapters", []):
            repo = ch.get("repo", "")
            subdir = ch.get("chapter_subdir", "")
            entry = ch.get("entry_file", "")
            if not _SAFE_REPO.match(repo):
                raise ValueError(f"Invalid repo name: {repo!r}")
            if subdir and (not _SAFE_PATH.match(subdir) or ".." in subdir):
                raise ValueError(f"Invalid chapter_subdir: {subdir!r}")
            if entry and (not _SAFE_PATH.match(entry) or ".." in entry):
                raise ValueError(f"Invalid entry_file: {entry!r}")


def _build_request_data(book, *, preview_structure: bool = False) -> dict:
    """Serialize a Book's chapter selection into the build_request.json schema.

    Automatically includes any foundational chapters that are listed in
    ``depends_on`` by the selected chapters but not already present in the
    book.  These are prepended as a "Foundations" part so that their
    ``\\label`` commands are available for cross-chapter ``\\ref`` resolution.

    When ``book.include_examples`` is True, attaches a list of PUBLISHED
    Examples to each chapter that has them, deduplicated so a multi-tag
    Example only renders under the earliest in-book chapter that includes
    it. ``book.include_solutions`` is propagated as a top-level flag for
    the template to consume.

    When ``preview_structure`` is True, the resulting payload signals
    that the build pipeline should render only the book skeleton (TOC +
    chapter titles, no body). Chapter titles are included so the stub
    main.tex can emit \\chapter{Title} for each entry.
    """
    from catalog.models import Example
    from catalog.services.dependencies import resolve_foundational_dependencies

    parts = []
    included_chabbrs: set[str] = set()
    # ordered list of chapter_id by book position; index gives "earliest" rank
    book_chapter_order: list[int] = []
    # chabbr values referenced by depends_on across the whole book
    seed_depends_on: list[str] = []

    for part in book.parts.order_by("order"):
        chapters = []
        for bc in part.book_chapters.order_by("order").select_related("chapter"):
            ch = bc.chapter
            chapters.append({
                "repo": ch.github_repo,
                "chapter_subdir": ch.chapter_subdir,
                "entry_file": ch.latex_entry_file,
                "title": ch.title,
                "_chapter_id": ch.id,
            })
            book_chapter_order.append(ch.id)
            seed_depends_on.extend(ch.depends_on)
            if ch.chabbr:
                included_chabbrs.add(ch.chabbr)
        parts.append({"title": part.title, "chapters": chapters})

    # Resolve foundational-chapter dependencies to full transitive closure,
    # topologically ordered (a prerequisite's prerequisite precedes it).
    dep_chapters = resolve_foundational_dependencies(included_chabbrs, seed_depends_on)
    if dep_chapters:
        dep_entries = [{
            "repo": ch.github_repo,
            "chapter_subdir": ch.chapter_subdir,
            "entry_file": ch.latex_entry_file,
            "title": ch.title,
            "_chapter_id": ch.id,
        } for ch in dep_chapters]
        # Prepend a Foundations part so labels are defined before they are
        # referenced by topical chapters.
        parts.insert(0, {"title": "Foundations", "chapters": dep_entries})
        book_chapter_order = [ch.id for ch in dep_chapters] + book_chapter_order

    # ── Worked-examples integration ─────────────────────────────────────
    # Build a chapter_id -> [example dict] map honoring the
    # earliest-in-book rule for cross-chapter examples.
    chapter_examples: dict[int, list[dict]] = {cid: [] for cid in book_chapter_order}

    if getattr(book, "include_examples", True) and book_chapter_order:
        rank = {cid: i for i, cid in enumerate(book_chapter_order)}
        excluded = set(getattr(book, "excluded_example_ids", None) or [])
        candidate_examples = (
            Example.objects.filter(
                status=Example.Status.PUBLISHED,
                chapters__in=book_chapter_order,
            )
            .prefetch_related("chapters", "figures")
            .distinct()
            .order_by("difficulty", "id")
        )
        for ex in candidate_examples:
            if ex.id in excluded:
                continue
            tagged_in_book = [
                ch.id for ch in ex.chapters.all() if ch.id in rank
            ]
            if not tagged_in_book:
                continue
            host = min(tagged_in_book, key=lambda cid: rank[cid])
            chapter_examples[host].append({
                "id": ex.id,
                "difficulty": ex.difficulty,
                "statement_tex": ex.statement_tex,
                "solution_tex": ex.solution_tex,
                "figures": [
                    {
                        "id": fig.id,
                        "original_filename": fig.original_filename,
                        "file_path": str(Path(fig.file.path)) if fig.file else "",
                    }
                    for fig in ex.figures.all()
                ],
            })

    # Strip private _chapter_id, swap in the resolved examples list
    for part in parts:
        for ch in part["chapters"]:
            cid = ch.pop("_chapter_id")
            ch["examples"] = chapter_examples.get(cid, [])

    return {
        "book_title": book.title,
        "include_examples": bool(getattr(book, "include_examples", True)),
        "include_solutions": bool(getattr(book, "include_solutions", True)),
        "preview_structure": preview_structure,
        "parts": parts,
    }


def _copy_example_figures(workdir: Path, request_data: dict, log_fn) -> None:
    """Copy each example's figures from media/example_figures/<id>/ into
    workdir/example_figures/<id>/ so the main.tex \\graphicspath wrap
    resolves \\includegraphics{filename} references at compile time.
    """
    target_root = workdir / "example_figures"
    count = 0
    for part in request_data.get("parts", []):
        for ch in part.get("chapters", []):
            for ex in ch.get("examples", []):
                figs = ex.get("figures") or []
                if not figs:
                    continue
                ex_dir = target_root / str(ex["id"])
                ex_dir.mkdir(parents=True, exist_ok=True)
                for fig in figs:
                    src = Path(fig["file_path"]) if fig.get("file_path") else None
                    if src is None or not src.is_file():
                        log_fn(f"  ! example {ex['id']} figure missing: {src}")
                        continue
                    shutil.copy2(src, ex_dir / fig["original_filename"])
                    count += 1
    if count:
        log_fn(f"Copied {count} example figure(s) into example_figures/")


def _run(cmd: list[str], log_fn, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """
    Run *cmd* as a subprocess, append stdout/stderr to the build log, and
    raise ``subprocess.CalledProcessError`` on non-zero exit.
    """
    log_fn(f"$ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.stdout:
        log_fn(result.stdout.rstrip())
    if result.stderr:
        log_fn(result.stderr.rstrip())
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def _run_script(
    script: Path,
    workdir: Path,
    log_fn,
    extra_args: list[str] | None = None,
) -> None:
    """Run a Python build script with --workdir and optional extra args."""
    cmd = [sys.executable, str(script), "--workdir", str(workdir)]
    if extra_args:
        cmd.extend(extra_args)
    _run(cmd, log_fn)


# Total attempts (initial + retries) for a single `git clone`. GitHub
# occasionally returns 5xx ("Internal Server Error"), which is almost
# always transient — three tries with exponential backoff covers it.
_CLONE_MAX_ATTEMPTS = 3
_CLONE_BACKOFF_BASE = 2  # seconds; doubles each attempt


def _cache_dir_for_repo(repo: str) -> Path:
    """Path to the persistent warm-clone for *repo* under GIT_CACHE_DIR.

    The repo name (e.g. "OpenChapters/OpenChapters") is flattened to a
    single directory name with `/` → `__` so all caches live as
    siblings under one mount point. Whitespace-free identifier means
    no shell-quoting subtleties downstream.
    """
    safe = repo.replace("/", "__")
    return Path(settings.GIT_CACHE_DIR) / safe


def _clone_repo(clone_url: str, repo_dir: Path, log_fn) -> None:
    """`git clone --depth=1` with exponential-backoff retry.

    Retries on any non-zero exit because git's exit codes don't
    distinguish transient network/server failures from genuine
    "repo not found". A wrong URL fails the same way three times in a
    row anyway; the small extra wait is acceptable to make a one-off
    GitHub 500 self-heal instead of failing the whole build.

    On final failure raises subprocess.CalledProcessError so the
    surrounding _build_step context manager records the failure on the
    BuildStep row exactly as before.
    """
    cmd = ["git", "clone", "--depth=1", clone_url, str(repo_dir)]
    last_exc: subprocess.CalledProcessError | None = None
    for attempt in range(1, _CLONE_MAX_ATTEMPTS + 1):
        # If a prior attempt left a partial directory, clear it so the
        # retry can write into a clean path.
        if repo_dir.exists():
            shutil.rmtree(repo_dir, ignore_errors=True)
        try:
            _run(cmd, log_fn)
            return
        except subprocess.CalledProcessError as exc:
            last_exc = exc
            if attempt >= _CLONE_MAX_ATTEMPTS:
                break
            backoff = _CLONE_BACKOFF_BASE * (2 ** (attempt - 1))
            log_fn(
                f"  ! git clone failed (attempt {attempt}/{_CLONE_MAX_ATTEMPTS}); "
                f"retrying in {backoff}s"
            )
            time.sleep(backoff)
    assert last_exc is not None
    raise last_exc


def _refresh_cache(clone_url: str, cache_dir: Path, log_fn) -> None:
    """Bring the warm-clone at *cache_dir* up to current origin/HEAD.

    First call (no cache_dir yet): does a shallow clone via _clone_repo.
    Subsequent calls: `git fetch --depth=1 origin` then a hard reset to
    FETCH_HEAD so the working tree matches upstream byte-for-byte. If
    the fetch path fails for any reason (corrupted cache, history
    rewrite, etc.) the directory is wiped and a fresh clone takes its
    place — slow but self-healing.

    Concurrency: callers must hold a per-cache fcntl.flock so two
    builds for the same repo don't fight over the working tree. See
    _materialize_via_cache for the wrapper that handles the lock.
    """
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    if not (cache_dir / ".git").is_dir():
        _clone_repo(clone_url, cache_dir, log_fn)
        return
    try:
        _run(["git", "-C", str(cache_dir), "fetch", "--depth=1", "origin"], log_fn)
        _run(["git", "-C", str(cache_dir), "reset", "--hard", "FETCH_HEAD"], log_fn)
        # `git clean -fdx` removes everything not tracked, including any
        # stray files a prior build's post-clone scripts may have written.
        _run(["git", "-C", str(cache_dir), "clean", "-fdx"], log_fn)
    except subprocess.CalledProcessError:
        log_fn("  ! warm cache refresh failed; rebuilding from scratch")
        shutil.rmtree(cache_dir, ignore_errors=True)
        _clone_repo(clone_url, cache_dir, log_fn)


def _resolve_repo_sha(repo_dir: Path) -> str:
    """Return the resolved HEAD commit SHA for a cloned repo, or '' on error."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=10,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _materialize_via_cache(clone_url: str, repo: str, target_dir: Path, log_fn) -> None:
    """Update the warm cache for *repo* and hardlink it into *target_dir*.

    Replaces the previous "git clone --depth=1 directly into the build
    workspace" path: instead of pulling tens of megabytes from GitHub
    on every build, refresh a persistent clone once and `cp -al` it
    into the workspace — hardlinks share inodes so this is effectively
    instant and uses no extra disk until the build modifies a file
    (figures, generated .aux, etc.) and copy-on-write kicks in.

    Acquires an exclusive fcntl.flock on the per-repo cache so two
    concurrent build_book runs for the same repo can't race on the
    `git fetch` + `git reset` sequence.
    """
    import fcntl

    cache_dir = _cache_dir_for_repo(repo)
    lock_path = cache_dir.parent / f"{cache_dir.name}.lock"
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    # Open the lockfile (created on first use) — flock-on-fd, so the
    # lock is released when fd_lock falls out of scope at function exit.
    with open(lock_path, "w") as fd_lock:
        fcntl.flock(fd_lock.fileno(), fcntl.LOCK_EX)
        _refresh_cache(clone_url, cache_dir, log_fn)
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        # Prefer hardlinks (cp -al) when the cache and the workspace
        # share a filesystem — instant + zero extra disk. In Docker
        # the cache typically sits on a named volume while builds
        # write to /tmp on the container's overlay; hardlinks across
        # that boundary fail with "Invalid cross-device link", so
        # fall back to a plain recursive copy (cp -a). Still a small
        # fraction of the original clone-from-GitHub cost.
        try:
            same_fs = cache_dir.stat().st_dev == target_dir.parent.stat().st_dev
        except OSError:
            same_fs = False
        cp_flag = "-al" if same_fs else "-a"
        _run(["cp", cp_flag, str(cache_dir), str(target_dir)], log_fn)
        # The hardlinked / copied tree includes .git, which downstream
        # scripts don't care about — leaving it is harmless and lets us
        # inspect the resolved commit from inside a failed build's
        # archive.


def _prune_unavailable_chapters(workdir: Path, request_data: dict, log_fn) -> list[dict]:
    """Drop chapters whose LaTeX source isn't present in the freshly-cloned
    repos and return a record of what was dropped.

    A chapter can be selected for a book and then have its source removed
    from the OpenChapters repo before the next build. The catalog row
    survives (and sync unpublishes it), but the .tex is gone — so a rebuild
    would otherwise die deep inside LaTeX with "can't find file". Instead we
    skip the chapter and let the rest of the book build, recording each
    omission so the user can be told (and prompted to find a replacement).

    A chapter's entry file lives at ``<workdir>/<repo-last-segment>/<entry_file>``
    — the same path build_main_tex.py turns into the ``\\include{}`` target.
    Mutates *request_data* in place: removes omitted chapters and then any
    part left with no chapters (including an emptied auto-added Foundations).
    """
    omitted: list[dict] = []
    for part in request_data.get("parts", []):
        kept = []
        for ch in part.get("chapters", []):
            entry = ch.get("entry_file", "")
            repo = ch.get("repo", "")
            entry_path = workdir / repo.split("/")[-1] / entry if entry else None
            if entry_path is not None and entry_path.is_file():
                kept.append(ch)
                continue
            info = {
                "title": ch.get("title") or ch.get("chapter_subdir") or entry or repo,
                "repo": repo,
                "subdir": ch.get("chapter_subdir", ""),
                "reason": "source not found in repository",
            }
            omitted.append(info)
            log_fn(
                f'  ! omitting chapter "{info["title"]}" — '
                f'{entry or "(no entry file)"} not found in {repo}'
            )
        part["chapters"] = kept
    request_data["parts"] = [p for p in request_data.get("parts", []) if p["chapters"]]
    return omitted


def _omitted_email_sections(omitted: list[dict]) -> tuple[str, str]:
    """Return (plain-text, html) snippets noting chapters left out of a build.

    Empty strings when nothing was omitted, so callers can unconditionally
    interpolate the result into the email body.
    """
    if not omitted:
        return "", ""
    from html import escape

    titles = [o.get("title") or o.get("subdir") or o.get("repo") or "?" for o in omitted]
    text = (
        "Note: the following chapter(s) could not be included because their "
        "source is no longer available in the repository:\n"
        + "".join(f"  - {t}\n" for t in titles)
        + "The rest of your book was built as usual. You may want to look for a "
        "replacement chapter on similar topics.\n\n"
    )
    items = "".join(f"<li>{escape(str(t))}</li>" for t in titles)
    html_section = (
        '<div style="margin-top:16px;padding:12px 16px;background-color:#fffbeb;'
        'border:1px solid #fde68a;border-radius:6px;">'
        "<p style=\"margin:0 0 6px;font-size:14px;color:#92400e;\"><strong>Some chapters "
        "were omitted</strong></p>"
        '<p style="margin:0 0 6px;font-size:13px;color:#92400e;">These chapters could '
        "not be included because their source is no longer available in the repository:</p>"
        f'<ul style="margin:0 0 6px 18px;font-size:13px;color:#92400e;">{items}</ul>'
        '<p style="margin:0;font-size:13px;color:#92400e;">The rest of your book was '
        "built as usual — you may want to look for a replacement chapter on similar topics.</p>"
        "</div>"
    )
    return text, html_section


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="books.build_book",
    time_limit=1800,       # hard kill after 30 min
    soft_time_limit=1500,  # SoftTimeLimitExceeded raised at 25 min
)
def build_book(self, book_id: int, preview_structure: bool = False) -> None:
    """
    Full LaTeX build pipeline for a Book.

    Pipeline:
      1. Create isolated temp workspace /tmp/ocbuild-<uuid>/
      2. Copy .sty / .ins / .ist template files into workspace
      3. Write build_request.json
      4. Clone the chapter monorepo (single shallow clone)
      5. Copy matter/ from the cloned repo into the workspace
      6. Run concat_bibs.py      → OpenChapters.bib
      7. Run collect_images.py   → ImageFolder/
      8. Run build_main_tex.py   → main.tex
      9. Run generate_gin.py     → gitHeadLocal.gin
     10. Run arara on main.tex
     11. Store PDF, update BuildJob + Book status
     12. Trigger deliver_pdf
     13. Clean up temp workspace

    When ``preview_structure`` is True, the pipeline takes a fast-path
    variant that renders only the book's frontmatter + TOC + chapter
    titles. The clone step still pulls the chapter repos (so the
    matter/, cover, and .sty assets from the monorepo are available),
    but the generated main.tex uses ``main_structure.tex.j2`` and the
    arara run drops biber + makeindex + extra pdflatex passes. The
    resulting PDF is saved alongside regular PDFs but flagged on
    BuildJob so the UI can label it accordingly. Email delivery is
    skipped for previews.
    """
    from books.models import Book, BuildJob

    # ── Load book & create / reset BuildJob ──────────────────────────────────
    try:
        book = Book.objects.select_related("user").get(id=book_id)
    except Book.DoesNotExist:
        logger.error("build_book: Book %d not found", book_id)
        return

    job, _ = BuildJob.objects.get_or_create(book=book)
    job.celery_task_id = self.request.id or ""
    job.started_at = timezone.now()
    job.finished_at = None
    job.pdf_path = ""
    job.log_output = ""
    job.error_message = ""
    job.omitted_chapters = []
    job.preview_structure = preview_structure
    job.save()
    _reset_steps(job)

    book.status = Book.Status.BUILDING
    book.save(update_fields=["status"])

    # ── Build setup ───────────────────────────────────────────────────────────
    build_id = str(uuid.uuid4())
    workdir = Path(f"/tmp/ocbuild-{build_id}")
    log_lines: list[str] = []

    def log(msg: str) -> None:
        log_lines.append(msg)
        logger.info("[build %s] %s", build_id[:8], msg)

    scripts_dir = Path(settings.BUILD_SCRIPTS_DIR)
    template_dir = Path(settings.BUILD_TEMPLATE_DIR)
    output_dir = Path(settings.BUILD_OUTPUT_DIR)

    try:
        # ── Step 0: setup workspace + validated request payload ─────────────
        with _build_step(job, name="setup", label="Preparing workspace",
                         order=0, log_lines=log_lines):
            workdir.mkdir(parents=True, exist_ok=False)
            log(f"Workspace: {workdir}")

            for f in template_dir.iterdir():
                if f.is_file():
                    shutil.copy2(f, workdir / f.name)
            log(f"Copied template files from {template_dir}")

            request_data = _build_request_data(
                book, preview_structure=preview_structure,
            )
            (workdir / "build_request.json").write_text(
                json.dumps(request_data, indent=2), encoding="utf-8"
            )
            log("Wrote build_request.json")
            if preview_structure:
                log("Structure preview mode — TOC + chapter titles only.")

            _validate_build_data(request_data)
            log("Validated build request data")

        # ── Step 1: clone chapter repos ──────────────────────────────────────
        with _build_step(job, name="clone", label="Cloning chapter sources",
                         order=1, log_lines=log_lines) as step:
            from catalog.git_provider import get_provider
            provider = get_provider()
            repos = sorted({
                ch["repo"]
                for p in request_data["parts"]
                for ch in p["chapters"]
            })
            chapter_shas: dict[str, str] = {}
            for i, repo in enumerate(repos, start=1):
                _set_step_detail(step, f"{i} of {len(repos)}: {repo}")
                repo_dir = workdir / repo.split("/")[-1]
                _materialize_via_cache(
                    provider.clone_url(repo), repo, repo_dir, log,
                )
                sha = _resolve_repo_sha(repo_dir)
                if sha:
                    chapter_shas[repo] = sha
                    log(f"  resolved {repo} @ {sha[:8]}")
            job.chapter_shas = chapter_shas
            job.save(update_fields=["chapter_shas"])
            _set_step_detail(step, f"{len(repos)} repositor{'y' if len(repos)==1 else 'ies'}")

        # ── Step 1b: drop chapters whose source is no longer in the repo ─────
        # Skip-and-warn: keep building the rest of the book, but record any
        # omission so the user is told (and can hunt for a replacement).
        omitted = _prune_unavailable_chapters(workdir, request_data, log)
        if omitted:
            job.omitted_chapters = omitted
            job.save(update_fields=["omitted_chapters"])
            (workdir / "build_request.json").write_text(
                json.dumps(request_data, indent=2), encoding="utf-8"
            )
            log(f"Omitted {len(omitted)} unavailable chapter(s); rewrote build_request.json")
            if not request_data["parts"]:
                raise RuntimeError(
                    "All selected chapters are unavailable — their source has been "
                    "removed from the repository, so there is nothing to typeset."
                )

        # ── Step 2: assemble matter/, frontmatter, cover, bibs, figures ──────
        with _build_step(job, name="assemble", label="Assembling chapters and figures",
                         order=2, log_lines=log_lines):
            monorepo_dir = workdir / "OpenChapters"
            matter_src = monorepo_dir / "Build" / "matter"
            if not matter_src.is_dir():
                raise FileNotFoundError(
                    f"matter/ not found in cloned repo at {matter_src}. "
                    "Expected OpenChapters/Build/matter/ to exist in the monorepo."
                )

            def _skip_symlinks(src: str, names: list) -> set:
                """Ignore symlinks to avoid circular references (e.g. matter/matter)."""
                return {n for n in names if os.path.islink(os.path.join(src, n))}

            shutil.copytree(matter_src, workdir / "matter", ignore=_skip_symlinks)
            log(f"Copied matter/ from {matter_src}")

            # Frontmatter.tex.template → Frontmatter.tex (cover, title, author)
            fm_template = workdir / "matter" / "Frontmatter.tex.template"
            fm_output = workdir / "matter" / "Frontmatter.tex"
            if fm_template.is_file():
                cover_filename = "background.pdf"
                if book.cover_image:
                    cover_filename = Path(book.cover_image.name).name
                fm_text = fm_template.read_text()
                fm_text = fm_text.replace("##COVERIMAGE##", cover_filename)
                fm_text = fm_text.replace("##BOOKTITLE##", book.title)
                fm_text = fm_text.replace("##USERNAME##", book.user.full_name or book.user.email)
                fm_output.write_text(fm_text)
                log(f"Processed Frontmatter.tex (cover={cover_filename}, title={book.title}, user={book.user.full_name or book.user.email})")

            img_folder = workdir / "ImageFolder"
            img_folder.mkdir(exist_ok=True)
            if book.cover_image:
                cover_src = Path(book.cover_image.path)
                if cover_src.is_file():
                    shutil.copy2(str(cover_src), str(img_folder / Path(book.cover_image.name).name))
                    log(f"Copied user cover image to ImageFolder/{Path(book.cover_image.name).name}")

            _run_script(scripts_dir / "concat_bibs.py", workdir, log)
            _run_script(scripts_dir / "collect_images.py", workdir, log)
            _copy_example_figures(workdir, request_data, log)

        # ── Step 3: generate main.tex + git metadata ─────────────────────────
        with _build_step(job, name="generate", label="Generating main.tex",
                         order=3, log_lines=log_lines):
            _run_script(
                scripts_dir / "build_main_tex.py", workdir, log,
                extra_args=["--build-id", build_id],
            )
            _run_script(
                scripts_dir / "generate_gin.py", workdir, log,
                extra_args=["--build-id", build_id],
            )

        # ── Step 4: typeset (the long one) ───────────────────────────────────
        with _build_step(job, name="typeset", label="Typesetting with LaTeX (arara)",
                         order=4, log_lines=log_lines):
            # -w enables whole-file directive scanning (pre-7.0 default).
            try:
                _run(["arara", "-w", "main.tex"], log, cwd=workdir)
            except subprocess.CalledProcessError:
                tex_log = workdir / "main.log"
                if tex_log.exists():
                    log_text = tex_log.read_text(errors="replace")
                    lines = log_text.splitlines()
                    error_lines = []
                    for i, line in enumerate(lines):
                        if line.startswith("!") or "Fatal error" in line:
                            start = max(0, i - 2)
                            end = min(len(lines), i + 6)
                            error_lines.extend(lines[start:end])
                            error_lines.append("---")
                    if error_lines:
                        log("--- LaTeX errors from main.log ---")
                        log("\n".join(error_lines[:80]))
                    else:
                        log("--- Last 30 lines of main.log ---")
                        log("\n".join(lines[-30:]))
                raise

        # ── Step 5: finalize (move PDF, update job/book) ─────────────────────
        with _build_step(job, name="finalize", label="Finalizing PDF",
                         order=5, log_lines=log_lines):
            pdf_src = workdir / "main.pdf"
            if not pdf_src.exists():
                raise FileNotFoundError(
                    "arara completed without error but main.pdf was not found"
                )

            output_dir.mkdir(parents=True, exist_ok=True)
            preview_tag = "structure_" if preview_structure else ""
            pdf_filename = f"book_{book.id}_{preview_tag}{build_id[:8]}.pdf"
            pdf_dst = output_dir / pdf_filename
            shutil.copy2(pdf_src, pdf_dst)
            log(f"PDF saved: {pdf_dst}")

            job.pdf_path = str(pdf_dst)
            job.finished_at = timezone.now()
            job.log_output = "\n".join(log_lines)
            job.save()

            book.status = Book.Status.COMPLETE
            book.save(update_fields=["status"])
            log("Build complete.")

        # Trigger email delivery — skipped for structure previews, which
        # are an in-app iteration tool, not something the user wants
        # mailed to them.
        if not preview_structure:
            deliver_pdf.delay(book.id)

    except SoftTimeLimitExceeded:
        error_msg = "Build exceeded 25-minute time limit and was cancelled."
        log(f"BUILD TIMEOUT: {error_msg}")

        job.error_message = error_msg
        job.finished_at = timezone.now()
        job.log_output = "\n".join(log_lines)
        job.save()

        book.status = Book.Status.FAILED
        book.save(update_fields=["status"])

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        log(f"BUILD FAILED: {error_msg}")

        job.error_message = error_msg
        job.finished_at = timezone.now()
        job.log_output = "\n".join(log_lines)
        job.save()

        book.status = Book.Status.FAILED
        book.save(update_fields=["status"])

        raise  # re-raise so Celery marks the task as FAILURE

    finally:
        # 13. Clean up temp workspace regardless of outcome
        if workdir.exists():
            # Archive failed builds for debugging (keep last 5)
            if book.status == Book.Status.FAILED:
                archive_dir = Path(str(settings.BUILD_OUTPUT_DIR)) / "failed_builds"
                archive_dir.mkdir(parents=True, exist_ok=True)
                archive_path = archive_dir / f"{build_id[:8]}"
                try:
                    if archive_path.exists():
                        shutil.rmtree(archive_path)
                    # Copy only the log and main.tex, not the full clone
                    archive_path.mkdir()
                    for name in ["main.log", "main.tex", "build_request.json"]:
                        src = workdir / name
                        if src.exists():
                            shutil.copy2(src, archive_path / name)
                    log_file = archive_path / "build.log"
                    log_file.write_text("\n".join(log_lines))
                    logger.info("[build %s] Archived failed build to %s", build_id[:8], archive_path)
                    # Prune old archives (keep last 10)
                    archives = sorted(archive_dir.iterdir(), key=lambda p: p.stat().st_mtime)
                    for old in archives[:-10]:
                        shutil.rmtree(old, ignore_errors=True)
                except Exception:
                    logger.exception("[build %s] Failed to archive build", build_id[:8])
            shutil.rmtree(workdir, ignore_errors=True)
            logger.info("[build %s] Cleaned up %s", build_id[:8], workdir)


@shared_task(
    bind=True,
    name="books.deliver_pdf",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=60,
    retry_backoff_max=600,
)
def deliver_pdf(self, book_id: int) -> None:
    """
    Send the user an email with a signed download link for their completed PDF.

    Uses the configured SMTP server if EMAIL_HOST is set; otherwise logs only.
    The download link is signed with Django's SECRET_KEY and expires after
    PDF_LINK_EXPIRY_DAYS (default 7 days).
    """
    from books.models import Book
    from books.signing import make_download_token

    try:
        book = Book.objects.select_related("user", "build_job").get(id=book_id)
    except Book.DoesNotExist:
        logger.error("deliver_pdf: Book %d not found", book_id)
        return

    if book.status != Book.Status.COMPLETE:
        logger.warning("deliver_pdf: Book %d is not complete (status=%s)", book_id, book.status)
        return

    # Build the signed download URL
    token = make_download_token(book.id, book.user_id)
    site_url = getattr(settings, "SITE_URL", "http://localhost:5173").rstrip("/")
    download_url = f"{site_url}/api/dl/{token}/"
    expiry_days = getattr(settings, "PDF_LINK_EXPIRY_DAYS", 7)

    if not getattr(settings, "EMAIL_HOST", ""):
        logger.info(
            "deliver_pdf: EMAIL_HOST not set; would email %s download link %s",
            book.user.email,
            download_url,
        )
        return

    from django.core.mail import EmailMultiAlternatives

    omitted = getattr(getattr(book, "build_job", None), "omitted_chapters", None) or []
    omitted_text, omitted_html = _omitted_email_sections(omitted)

    from_email = getattr(settings, "FROM_EMAIL", "noreply@openchapters.org")
    subject = f"Your book is ready: {book.title}"
    text_body = (
        f"Hi,\n\n"
        f'Your book "{book.title}" has been typeset and is ready for download.\n\n'
        f"Download your PDF:\n{download_url}\n\n"
        f"This link expires in {expiry_days} days.\n\n"
        f"{omitted_text}"
        f"— OpenChapters"
    )
    html_body = (
        f"<p>Hi,</p>"
        f'<p>Your book <strong>{book.title}</strong> has been typeset and is ready for download.</p>'
        f'<p><a href="{download_url}" style="display:inline-block;padding:12px 24px;'
        f"background-color:#2563eb;color:#ffffff;text-decoration:none;border-radius:6px;"
        f'font-weight:600;">Download PDF</a></p>'
        f"<p><small>This link expires in {expiry_days} days. "
        f"You can also download from your <a href=\"{site_url}/library\">Library</a>.</small></p>"
        f"{omitted_html}"
        f"<p>— OpenChapters</p>"
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=f"OpenChapters <{from_email}>",
        to=[book.user.email],
    )
    msg.attach_alternative(html_body, "text/html")

    try:
        msg.send()
        logger.info("deliver_pdf: email sent to %s", book.user.email)
    except Exception as exc:
        logger.error(
            "deliver_pdf: SMTP error for book %d (attempt %d/%d): %s",
            book_id, self.request.retries + 1, 3, exc,
        )
        raise  # triggers autoretry


# ---------------------------------------------------------------------------
# Per-book HTML build (lwarp)
# ---------------------------------------------------------------------------

def _convert_pdfs_to_svg(image_dir: Path, log_fn) -> None:
    """Convert all PDF figures in *image_dir* to SVG using pdf2svg.

    lwarp's HTML output references figures as SVG (not PDF), so this
    conversion must happen before arara runs.
    """
    count = 0
    for pdf_file in sorted(image_dir.glob("*.pdf")):
        svg_file = pdf_file.with_suffix(".svg")
        if svg_file.exists():
            continue
        try:
            subprocess.run(
                ["pdf2svg", str(pdf_file), str(svg_file)],
                capture_output=True,
                check=True,
                timeout=30,
            )
            count += 1
        except FileNotFoundError:
            log_fn("WARNING: pdf2svg not installed — skipping SVG conversion")
            return
        except subprocess.CalledProcessError as e:
            log_fn(f"  pdf2svg failed for {pdf_file.name}: {e.stderr!r}")
        except subprocess.TimeoutExpired:
            log_fn(f"  pdf2svg timed out for {pdf_file.name}")
    log_fn(f"Converted {count} PDF figures to SVG")


_MATHJAX_SCRIPT_RE = re.compile(
    r"<script>\s*\n\s*// Lwarp MathJax emulation code.*?</script>",
    re.DOTALL,
)


def _externalize_mathjax_config(workdir: Path, log_fn) -> None:
    """Extract lwarp's inline MathJax <script> block to lwarp_mathjax.js.

    lwarp emits the MathJax setup (tags="ams", tagformat, \\seteqnumber
    handler, custom delimiters) as an inline <script> at the top of every
    generated HTML file. Production CSP omits script-src 'unsafe-inline',
    so the browser blocks that block — MathJax then starts with defaults
    (tags='none') and equations render without numbers. Moving the block
    to an external file keeps the same config while satisfying CSP.
    """
    external_js = workdir / "lwarp_mathjax.js"
    replacement = '<script src="lwarp_mathjax.js"></script>'
    wrote_js = False
    rewritten = 0
    for html_file in workdir.glob("*.html"):
        content = html_file.read_text(encoding="utf-8", errors="replace")
        match = _MATHJAX_SCRIPT_RE.search(content)
        if not match:
            continue
        if not wrote_js:
            inner = match.group(0)
            inner = inner[len("<script>"):-len("</script>")].strip("\n")
            external_js.write_text(inner + "\n", encoding="utf-8")
            wrote_js = True
        html_file.write_text(
            content[: match.start()] + replacement + content[match.end():],
            encoding="utf-8",
        )
        rewritten += 1
    log_fn(f"Externalized MathJax config into lwarp_mathjax.js across {rewritten} HTML file(s)")


def _postprocess_book_html(workdir: Path, log_fn) -> None:
    """Link the ocweb_overrides stylesheet + sidetoc JS into every HTML file,
    and externalize lwarp's inline MathJax config.

    All assets are referenced by external URL (not inlined) so the
    production CSP — which omits ``script-src 'unsafe-inline'`` — does
    not block them.
    """
    _externalize_mathjax_config(workdir, log_fn)
    css_link = '<link rel="stylesheet" type="text/css" href="ocweb_overrides.css" />'
    js_link = '<script defer src="ocweb_sidetoc.js"></script>'
    injection = css_link + "\n" + js_link
    injected = 0
    for html_file in workdir.glob("*.html"):
        content = html_file.read_text(encoding="utf-8", errors="replace")
        if "ocweb_overrides.css" in content:
            continue
        if "</head>" in content:
            content = content.replace("</head>", f"{injection}\n</head>", 1)
            html_file.write_text(content, encoding="utf-8")
            injected += 1
    log_fn(f"Linked ocweb_overrides.css + ocweb_sidetoc.js into {injected} HTML file(s)")


def _write_html_gin(workdir: Path, build_id: str) -> None:
    """Write a lwarp-safe gitHeadLocal.gin.

    gitinfo2's [local] option loads gitHeadLocal.gin at package-load
    time. The PDF build uses a ``\\usepackage[...]{gitexinfo}`` block,
    but lwarp strips and rejects braces in package options. Instead we
    emit ``\\renewcommand`` for each gitinfo2 field, matching the
    style used by ``build_chapter_html``.
    """
    from datetime import datetime, timezone as tz

    now = datetime.now(tz.utc)
    short_id = build_id[:7]
    content = (
        f"\\usepackage{{gitinfo2}}\n"
        f"\\renewcommand{{\\gitAbbrevHash}}{{{short_id}}}\n"
        f"\\renewcommand{{\\gitHash}}{{{build_id}}}\n"
        f"\\renewcommand{{\\gitAuthorName}}{{OpenChapters Web}}\n"
        f"\\renewcommand{{\\gitAuthorEmail}}{{noreply@openchapters.org}}\n"
        f"\\renewcommand{{\\gitAuthorDate}}{{{now.strftime('%Y-%m-%d')}}}\n"
        f"\\renewcommand{{\\gitAuthorIsoDate}}{{{now.isoformat()}}}\n"
        f"\\renewcommand{{\\gitRel}}{{web-{now.strftime('%Y-%m-%d')}}}\n"
        f"\\renewcommand{{\\gitRoff}}{{0}}\n"
    )
    (workdir / "gitHeadLocal.gin").write_text(content, encoding="utf-8")


def _zip_directory(source_dir: Path, zip_path: Path) -> None:
    """Create a zip archive of *source_dir* at *zip_path*.

    Entries are stored with paths relative to *source_dir* so the archive
    unpacks into a clean top-level directory.
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(source_dir):
            root_path = Path(root)
            for name in files:
                file_path = root_path / name
                arcname = file_path.relative_to(source_dir)
                zf.write(file_path, arcname)


@shared_task(
    bind=True,
    name="books.build_book_html",
    time_limit=1800,
    soft_time_limit=1500,
)
def build_book_html(self, book_id: int, send_email: bool = True) -> None:
    """
    Per-book HTML build pipeline via lwarp.

    Mirrors ``build_book`` but renders the HTML-specific Jinja2 template
    and collects lwarp output (HTML files + SVG assets) into
    ``<BUILD_HTML_OUTPUT_DIR>/book_<id>/``. A zip archive of that output
    is written alongside so it can be downloaded as a single file.

    ``send_email=False`` suppresses the deliver_book_html notification —
    used when this task is chained after ``build_book`` so the user only
    gets the PDF email (the View Online link is already in the UI).
    """
    from books.models import Book, BuildJob

    try:
        book = Book.objects.select_related("user").get(id=book_id)
    except Book.DoesNotExist:
        logger.error("build_book_html: Book %d not found", book_id)
        return

    job, _ = BuildJob.objects.get_or_create(book=book)
    job.celery_task_id = self.request.id or ""
    job.started_at = timezone.now()
    job.finished_at = None
    job.log_output = ""
    job.error_message = ""
    job.omitted_chapters = []
    job.save()
    _reset_steps(job)

    book.status = Book.Status.BUILDING
    book.save(update_fields=["status"])

    build_id = str(uuid.uuid4())
    workdir = Path(f"/tmp/ocbuild-html-{build_id}")
    log_lines: list[str] = []

    def log(msg: str) -> None:
        log_lines.append(msg)
        logger.info("[book-html %s] %s", build_id[:8], msg)

    scripts_dir = Path(settings.BUILD_SCRIPTS_DIR)
    template_dir = Path(settings.BUILD_TEMPLATE_DIR)
    template_html_dir = Path(settings.BUILD_TEMPLATE_HTML_DIR)
    html_output_root = Path(settings.BUILD_HTML_OUTPUT_DIR)

    try:
        # ── Step 0: setup workspace + validated request payload ──────────
        with _build_step(job, name="setup", label="Preparing workspace",
                         order=0, log_lines=log_lines):
            workdir.mkdir(parents=True, exist_ok=False)
            log(f"Workspace: {workdir}")

            for f in template_html_dir.iterdir():
                if f.is_file():
                    shutil.copy2(f, workdir / f.name)
            log(f"Copied HTML template files from {template_html_dir}")

            # Pull a small set of .sty files from the PDF template dir.
            for sty_name in ("arara.sty", "mytodonotes.sty", "StyleInd.ist"):
                sty_path = template_dir / sty_name
                if sty_path.is_file():
                    shutil.copy2(sty_path, workdir / sty_name)

            # Force latexmk runs (incl. via lwarpmk) to be non-interactive.
            (workdir / ".latexmkrc").write_text(
                "$pdflatex = 'pdflatex -interaction=nonstopmode -halt-on-error "
                "--shell-escape %O %S';\n",
                encoding="utf-8",
            )

            request_data = _build_request_data(book)
            (workdir / "build_request.json").write_text(
                json.dumps(request_data, indent=2), encoding="utf-8"
            )
            log("Wrote build_request.json")
            _validate_build_data(request_data)

        # ── Step 1: clone chapter repos ──────────────────────────────────
        with _build_step(job, name="clone", label="Cloning chapter sources",
                         order=1, log_lines=log_lines) as step:
            from catalog.git_provider import get_provider
            provider = get_provider()
            repos = sorted({
                ch["repo"]
                for p in request_data["parts"]
                for ch in p["chapters"]
            })
            chapter_shas: dict[str, str] = {}
            for i, repo in enumerate(repos, start=1):
                _set_step_detail(step, f"{i} of {len(repos)}: {repo}")
                repo_dir = workdir / repo.split("/")[-1]
                _materialize_via_cache(
                    provider.clone_url(repo), repo, repo_dir, log,
                )
                sha = _resolve_repo_sha(repo_dir)
                if sha:
                    chapter_shas[repo] = sha
                    log(f"  resolved {repo} @ {sha[:8]}")
            job.chapter_shas = chapter_shas
            job.save(update_fields=["chapter_shas"])
            _set_step_detail(step, f"{len(repos)} repositor{'y' if len(repos)==1 else 'ies'}")

        # ── Step 1b: drop chapters whose source is no longer in the repo ─────
        omitted = _prune_unavailable_chapters(workdir, request_data, log)
        if omitted:
            job.omitted_chapters = omitted
            job.save(update_fields=["omitted_chapters"])
            (workdir / "build_request.json").write_text(
                json.dumps(request_data, indent=2), encoding="utf-8"
            )
            log(f"Omitted {len(omitted)} unavailable chapter(s); rewrote build_request.json")
            if not request_data["parts"]:
                raise RuntimeError(
                    "All selected chapters are unavailable — their source has been "
                    "removed from the repository, so there is nothing to typeset."
                )

        # ── Step 2: assemble images, bibs, figures, SVG conversion ───────
        with _build_step(job, name="assemble", label="Assembling figures and bibliography",
                         order=2, log_lines=log_lines):
            # HTML builds skip matter/Frontmatter/Postmatter — the sidetoc
            # plus lwarp's landing page replace the PDF front cover.
            img_folder = workdir / "ImageFolder"
            img_folder.mkdir(exist_ok=True)

            _run_script(scripts_dir / "concat_bibs.py", workdir, log)
            _run_script(scripts_dir / "collect_images.py", workdir, log)
            _convert_pdfs_to_svg(img_folder, log)

            _copy_example_figures(workdir, request_data, log)
            if (workdir / "example_figures").is_dir():
                for ex_subdir in (workdir / "example_figures").iterdir():
                    if ex_subdir.is_dir():
                        _convert_pdfs_to_svg(ex_subdir, log)

        # ── Step 3: generate main.tex + git metadata ─────────────────────
        with _build_step(job, name="generate", label="Generating main.tex",
                         order=3, log_lines=log_lines):
            author = book.user.full_name or book.user.email
            _run_script(
                scripts_dir / "build_main_book_html_tex.py", workdir, log,
                extra_args=[
                    "--build-id", build_id,
                    "--book-author", author,
                ],
            )
            # generate_gin.py emits \usepackage[...]{gitexinfo}, which lwarp
            # rejects (no braces in package options). Use the HTML-safe
            # \renewcommand variant instead.
            _write_html_gin(workdir, build_id)

        # ── Step 4: typeset (arara → full lwarp chain) ───────────────────
        with _build_step(job, name="typeset", label="Typesetting (arara → lwarp → MathJax)",
                         order=4, log_lines=log_lines):
            env = os.environ.copy()
            env["OCBUILD_SCRIPTS_DIR"] = str(scripts_dir)
            env["PATH"] = "/usr/local/bin:" + env.get("PATH", "")
            # Isolate the Perl PAR cache per build so concurrent biber runs
            # don't clobber each other's module cache.
            par_cache = workdir / ".par_cache"
            par_cache.mkdir(exist_ok=True)
            env["PAR_GLOBAL_TEMP"] = str(par_cache)
            env["PAR_TEMP"] = str(par_cache)

            log("$ arara -w main.tex")
            result = subprocess.run(
                ["arara", "-w", "main.tex"],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                env=env,
                stdin=subprocess.DEVNULL,
                timeout=1500,
            )
            if result.stdout:
                log(result.stdout.rstrip())
            if result.stderr:
                log(result.stderr.rstrip())
            if result.returncode != 0:
                tex_log = workdir / "main.log"
                if tex_log.exists():
                    lines = tex_log.read_text(errors="replace").splitlines()
                    errs = [l for l in lines if l.startswith("!")][:10]
                    if errs:
                        log("--- LaTeX errors ---")
                        log("\n".join(errs))
                raise subprocess.CalledProcessError(result.returncode, ["arara", "main.tex"])

            index_html = workdir / "index.html"
            if not index_html.exists():
                raise FileNotFoundError("arara completed but index.html was not generated")

        # ── Step 5: bundle the HTML output into the live directory ───────
        with _build_step(job, name="bundle", label="Bundling HTML output",
                         order=5, log_lines=log_lines):
            _postprocess_book_html(workdir, log)

            html_output_root.mkdir(parents=True, exist_ok=True)
            output_dir = html_output_root / f"book_{book.id}"

            # Atomic swap via a temporary directory.
            tmp_dir = html_output_root / f".tmp-book-{book.id}-{build_id[:8]}"
            tmp_dir.mkdir(parents=True, exist_ok=False)

            try:
                for ext in ("*.html", "*.css", "*.js"):
                    for src in workdir.glob(ext):
                        shutil.copy2(src, tmp_dir / src.name)

                img_src = workdir / "ImageFolder"
                if img_src.is_dir():
                    img_dest = tmp_dir / "ImageFolder"
                    img_dest.mkdir()
                    for f in img_src.iterdir():
                        if f.suffix.lower() in (".svg", ".png") and f.is_file():
                            shutil.copy2(f, img_dest / f.name)

                ex_figures_src = workdir / "example_figures"
                if ex_figures_src.is_dir():
                    ex_figures_dest = tmp_dir / "example_figures"
                    ex_figures_dest.mkdir()
                    for ex_dir in ex_figures_src.iterdir():
                        if not ex_dir.is_dir():
                            continue
                        out_dir = ex_figures_dest / ex_dir.name
                        out_dir.mkdir()
                        for f in ex_dir.iterdir():
                            if f.suffix.lower() in (".svg", ".png", ".jpg", ".jpeg") and f.is_file():
                                shutil.copy2(f, out_dir / f.name)

                mathjax_txt = workdir / "lwarp_mathjax.txt"
                if mathjax_txt.exists():
                    shutil.copy2(mathjax_txt, tmp_dir / mathjax_txt.name)

                if not (tmp_dir / "index.html").exists():
                    raise RuntimeError("No index.html was copied to output")

                # Pre-build the zip archive so downloads are O(1).
                staging_zip = html_output_root / f".tmp-book-{book.id}-{build_id[:8]}.zip"
                _zip_directory(tmp_dir, staging_zip)
                shutil.move(str(staging_zip), str(tmp_dir / "book.zip"))
                log(f"Wrote zip archive ({(tmp_dir / 'book.zip').stat().st_size} bytes)")

                if output_dir.exists():
                    shutil.rmtree(output_dir)
                tmp_dir.rename(output_dir)
            except Exception:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                raise

            log(f"HTML output: {output_dir}")

        # ── Step 6: finalize (update Book + BuildJob) ───────────────────
        with _build_step(job, name="finalize", label="Finalizing",
                         order=6, log_lines=log_lines):
            book.html_path = str(output_dir)
            book.html_built_at = timezone.now()
            book.status = Book.Status.COMPLETE
            book.save(update_fields=["html_path", "html_built_at", "status"])

            job.finished_at = timezone.now()
            job.log_output = "\n".join(log_lines)
            job.save()

            log("HTML build complete.")

        # Email is a separate Celery task (not a step on this job).
        if send_email:
            deliver_book_html.delay(book.id)
        else:
            log("HTML email skipped (send_email=False).")

    except SoftTimeLimitExceeded:
        log("BUILD TIMEOUT: exceeded 25-minute time limit")
        job.error_message = "HTML build exceeded time limit."
        job.finished_at = timezone.now()
        job.log_output = "\n".join(log_lines)
        job.save()
        book.status = Book.Status.FAILED
        book.save(update_fields=["status"])

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        log(f"BUILD FAILED: {error_msg}")
        job.error_message = error_msg
        job.finished_at = timezone.now()
        job.log_output = "\n".join(log_lines)
        job.save()
        book.status = Book.Status.FAILED
        book.save(update_fields=["status"])
        raise

    finally:
        if workdir.exists():
            # Preserve log + main.tex on failure for debugging.
            if book.status == Book.Status.FAILED:
                archive_dir = html_output_root / "failed_builds"
                archive_dir.mkdir(parents=True, exist_ok=True)
                archive_path = archive_dir / build_id[:8]
                try:
                    if archive_path.exists():
                        shutil.rmtree(archive_path)
                    archive_path.mkdir()
                    for name in ("main.log", "main.tex", "build_request.json"):
                        src = workdir / name
                        if src.exists():
                            shutil.copy2(src, archive_path / name)
                    (archive_path / "build.log").write_text(
                        "\n".join(log_lines), encoding="utf-8"
                    )
                    archives = sorted(archive_dir.iterdir(), key=lambda p: p.stat().st_mtime)
                    for old in archives[:-10]:
                        shutil.rmtree(old, ignore_errors=True)
                except Exception:
                    logger.exception("[book-html %s] archive failed", build_id[:8])
            shutil.rmtree(workdir, ignore_errors=True)


@shared_task(
    bind=True,
    name="books.build_book_epub",
    time_limit=1800,
    soft_time_limit=1500,
)
def build_book_epub(self, book_id: int, send_email: bool = True) -> None:
    """
    Per-book EPUB build pipeline via tex4ebook.

    Reuses the PDF main.tex template (build_main_tex.py) since tex4ebook
    accepts standard LaTeX sources. The typeset step calls
    ``tex4ebook -f epub3 main.tex`` which internally invokes pdflatex
    plus the tex4ht/tex4ebook chain to emit main.epub. The resulting
    file is moved to ``<BUILD_EPUB_OUTPUT_DIR>/book_<id>_<hash>.epub``.

    ``send_email=False`` suppresses the deliver_epub notification — used
    when this task is chained after build_book/build_book_html so the
    user only receives one email per build batch.
    """
    from books.models import Book, BuildJob

    try:
        book = Book.objects.select_related("user").get(id=book_id)
    except Book.DoesNotExist:
        logger.error("build_book_epub: Book %d not found", book_id)
        return

    job, _ = BuildJob.objects.get_or_create(book=book)
    job.celery_task_id = self.request.id or ""
    job.started_at = timezone.now()
    job.finished_at = None
    job.log_output = ""
    job.error_message = ""
    job.omitted_chapters = []
    job.save()
    _reset_steps(job)

    book.status = Book.Status.BUILDING
    book.save(update_fields=["status"])

    build_id = str(uuid.uuid4())
    workdir = Path(f"/tmp/ocbuild-epub-{build_id}")
    log_lines: list[str] = []

    def log(msg: str) -> None:
        log_lines.append(msg)
        logger.info("[book-epub %s] %s", build_id[:8], msg)

    scripts_dir = Path(settings.BUILD_SCRIPTS_DIR)
    template_dir = Path(settings.BUILD_TEMPLATE_DIR)
    output_dir = Path(settings.BUILD_EPUB_OUTPUT_DIR)

    try:
        # ── Step 0: setup workspace ──────────────────────────────────────
        with _build_step(job, name="setup", label="Preparing workspace",
                         order=0, log_lines=log_lines):
            workdir.mkdir(parents=True, exist_ok=False)
            log(f"Workspace: {workdir}")

            for f in template_dir.iterdir():
                if f.is_file():
                    shutil.copy2(f, workdir / f.name)
            log(f"Copied template files from {template_dir}")

            request_data = _build_request_data(book)
            (workdir / "build_request.json").write_text(
                json.dumps(request_data, indent=2), encoding="utf-8"
            )
            _validate_build_data(request_data)
            log("Validated build request data")

        # ── Step 1: clone chapter repos + capture SHAs ───────────────────
        with _build_step(job, name="clone", label="Cloning chapter sources",
                         order=1, log_lines=log_lines) as step:
            from catalog.git_provider import get_provider
            provider = get_provider()
            repos = sorted({
                ch["repo"]
                for p in request_data["parts"]
                for ch in p["chapters"]
            })
            chapter_shas: dict[str, str] = {}
            for i, repo in enumerate(repos, start=1):
                _set_step_detail(step, f"{i} of {len(repos)}: {repo}")
                repo_dir = workdir / repo.split("/")[-1]
                _materialize_via_cache(provider.clone_url(repo), repo, repo_dir, log)
                sha = _resolve_repo_sha(repo_dir)
                if sha:
                    chapter_shas[repo] = sha
                    log(f"  resolved {repo} @ {sha[:8]}")
            job.chapter_shas = chapter_shas
            job.save(update_fields=["chapter_shas"])
            _set_step_detail(step, f"{len(repos)} repositor{'y' if len(repos)==1 else 'ies'}")

        # ── Step 2: assemble matter/, frontmatter, bibs, figures ─────────
        with _build_step(job, name="assemble", label="Assembling chapters and figures",
                         order=2, log_lines=log_lines):
            monorepo_dir = workdir / "OpenChapters"
            matter_src = monorepo_dir / "Build" / "matter"
            if not matter_src.is_dir():
                raise FileNotFoundError(
                    f"matter/ not found in cloned repo at {matter_src}"
                )

            def _skip_symlinks(src: str, names: list) -> set:
                return {n for n in names if os.path.islink(os.path.join(src, n))}

            shutil.copytree(matter_src, workdir / "matter", ignore=_skip_symlinks)

            fm_template = workdir / "matter" / "Frontmatter.tex.template"
            fm_output = workdir / "matter" / "Frontmatter.tex"
            if fm_template.is_file():
                cover_filename = "background.pdf"
                if book.cover_image:
                    cover_filename = Path(book.cover_image.name).name
                fm_text = fm_template.read_text()
                fm_text = fm_text.replace("##COVERIMAGE##", cover_filename)
                fm_text = fm_text.replace("##BOOKTITLE##", book.title)
                fm_text = fm_text.replace("##USERNAME##", book.user.full_name or book.user.email)
                fm_output.write_text(fm_text)

            img_folder = workdir / "ImageFolder"
            img_folder.mkdir(exist_ok=True)
            if book.cover_image:
                cover_src = Path(book.cover_image.path)
                if cover_src.is_file():
                    shutil.copy2(str(cover_src), str(img_folder / Path(book.cover_image.name).name))

            _run_script(scripts_dir / "concat_bibs.py", workdir, log)
            _run_script(scripts_dir / "collect_images.py", workdir, log)
            _copy_example_figures(workdir, request_data, log)

        # ── Step 3: generate main.tex + git metadata ─────────────────────
        with _build_step(job, name="generate", label="Generating main.tex",
                         order=3, log_lines=log_lines):
            _run_script(
                scripts_dir / "build_main_tex.py", workdir, log,
                extra_args=["--build-id", build_id],
            )
            _run_script(
                scripts_dir / "generate_gin.py", workdir, log,
                extra_args=["--build-id", build_id],
            )

        # ── Step 4: typeset with tex4ebook ───────────────────────────────
        with _build_step(job, name="typeset", label="Typesetting EPUB (tex4ebook)",
                         order=4, log_lines=log_lines):
            log("$ tex4ebook -f epub3 main.tex")
            result = subprocess.run(
                ["tex4ebook", "-f", "epub3", "main.tex"],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=1500,
            )
            if result.stdout:
                log(result.stdout.rstrip())
            if result.stderr:
                log(result.stderr.rstrip())
            if result.returncode != 0:
                tex_log = workdir / "main.log"
                if tex_log.exists():
                    lines = tex_log.read_text(errors="replace").splitlines()
                    errs = [l for l in lines if l.startswith("!")][:10]
                    if errs:
                        log("--- LaTeX errors ---")
                        log("\n".join(errs))
                raise subprocess.CalledProcessError(result.returncode, ["tex4ebook", "main.tex"])

        # ── Step 5: finalize (move EPUB, update Book + BuildJob) ─────────
        with _build_step(job, name="finalize", label="Finalizing EPUB",
                         order=5, log_lines=log_lines):
            epub_src = workdir / "main.epub"
            if not epub_src.exists():
                raise FileNotFoundError(
                    "tex4ebook completed without error but main.epub was not found"
                )

            output_dir.mkdir(parents=True, exist_ok=True)
            epub_filename = f"book_{book.id}_{build_id[:8]}.epub"
            epub_dst = output_dir / epub_filename
            shutil.copy2(epub_src, epub_dst)
            log(f"EPUB saved: {epub_dst}")

            job.epub_path = str(epub_dst)
            job.finished_at = timezone.now()
            job.log_output = "\n".join(log_lines)
            job.save()

            book.epub_path = str(epub_dst)
            book.epub_built_at = timezone.now()
            book.status = Book.Status.COMPLETE
            book.save(update_fields=["epub_path", "epub_built_at", "status"])
            log("EPUB build complete.")

        if send_email:
            deliver_epub.delay(book.id)
        else:
            log("EPUB email skipped (send_email=False).")

    except SoftTimeLimitExceeded:
        log("BUILD TIMEOUT: exceeded 25-minute time limit")
        job.error_message = "EPUB build exceeded time limit."
        job.finished_at = timezone.now()
        job.log_output = "\n".join(log_lines)
        job.save()
        book.status = Book.Status.FAILED
        book.save(update_fields=["status"])

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        log(f"BUILD FAILED: {error_msg}")
        job.error_message = error_msg
        job.finished_at = timezone.now()
        job.log_output = "\n".join(log_lines)
        job.save()
        book.status = Book.Status.FAILED
        book.save(update_fields=["status"])
        raise

    finally:
        if workdir.exists():
            if book.status == Book.Status.FAILED:
                archive_dir = output_dir / "failed_builds"
                archive_dir.mkdir(parents=True, exist_ok=True)
                archive_path = archive_dir / build_id[:8]
                try:
                    if archive_path.exists():
                        shutil.rmtree(archive_path)
                    archive_path.mkdir()
                    for name in ("main.log", "main.tex", "build_request.json"):
                        src = workdir / name
                        if src.exists():
                            shutil.copy2(src, archive_path / name)
                    (archive_path / "build.log").write_text(
                        "\n".join(log_lines), encoding="utf-8"
                    )
                    archives = sorted(archive_dir.iterdir(), key=lambda p: p.stat().st_mtime)
                    for old in archives[:-10]:
                        shutil.rmtree(old, ignore_errors=True)
                except Exception:
                    logger.exception("[book-epub %s] archive failed", build_id[:8])
            shutil.rmtree(workdir, ignore_errors=True)


@shared_task(
    bind=True,
    name="books.deliver_epub",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=60,
    retry_backoff_max=600,
)
def deliver_epub(self, book_id: int) -> None:
    """Email the user a link to download their book's EPUB output."""
    from books.models import Book
    from books.signing import make_download_token

    try:
        book = Book.objects.select_related("user").get(id=book_id)
    except Book.DoesNotExist:
        logger.error("deliver_epub: Book %d not found", book_id)
        return

    if not book.epub_built_at or not book.epub_path:
        logger.warning("deliver_epub: Book %d has no EPUB build", book_id)
        return

    token = make_download_token(book.id, book.user_id)
    site_url = getattr(settings, "SITE_URL", "http://localhost:5173").rstrip("/")
    download_url = f"{site_url}/api/dl-epub/{token}/"
    expiry_days = getattr(settings, "PDF_LINK_EXPIRY_DAYS", 7)

    if not getattr(settings, "EMAIL_HOST", ""):
        logger.info(
            "deliver_epub: EMAIL_HOST not set; would email %s download link %s",
            book.user.email, download_url,
        )
        return

    from django.core.mail import EmailMultiAlternatives

    from_email = getattr(settings, "FROM_EMAIL", "noreply@openchapters.org")
    subject = f"Your EPUB is ready: {book.title}"
    text_body = (
        f"Hi,\n\n"
        f'Your book "{book.title}" has been packaged as an EPUB '
        f"and is ready for download.\n\n"
        f"Download your EPUB:\n{download_url}\n\n"
        f"This link expires in {expiry_days} days.\n\n"
        f"— OpenChapters"
    )
    html_body = (
        f"<p>Hi,</p>"
        f'<p>Your book <strong>{book.title}</strong> has been packaged as an EPUB '
        f"and is ready for download.</p>"
        f'<p><a href="{download_url}" style="display:inline-block;padding:12px 24px;'
        f"background-color:#2563eb;color:#ffffff;text-decoration:none;border-radius:6px;"
        f'font-weight:600;">Download EPUB</a></p>'
        f"<p><small>This link expires in {expiry_days} days. "
        f'You can also download from your <a href="{site_url}/library">Library</a>.</small></p>'
        f"<p>— OpenChapters</p>"
    )

    msg = EmailMultiAlternatives(subject, text_body, from_email, [book.user.email])
    msg.attach_alternative(html_body, "text/html")
    msg.send()
    logger.info("deliver_epub: email sent to %s", book.user.email)


@shared_task(
    bind=True,
    name="books.deliver_book_html",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=60,
    retry_backoff_max=600,
)
def deliver_book_html(self, book_id: int) -> None:
    """Email the user a link to view and download their book's HTML output."""
    from books.models import Book

    try:
        book = Book.objects.select_related("user").get(id=book_id)
    except Book.DoesNotExist:
        logger.error("deliver_book_html: Book %d not found", book_id)
        return

    if not book.html_built_at:
        logger.warning("deliver_book_html: Book %d has no HTML build", book_id)
        return

    from books.signing import make_download_token

    site_url = getattr(settings, "SITE_URL", "http://localhost:5173").rstrip("/")
    view_url = f"{site_url}/books/{book.id}/read"
    # Signed token so the recipient can download without logging in.
    token = make_download_token(book.id, book.user_id)
    download_url = f"{site_url}/api/dl-html/{token}/"

    if not getattr(settings, "EMAIL_HOST", ""):
        logger.info(
            "deliver_book_html: EMAIL_HOST not set; would email %s: %s",
            book.user.email, view_url,
        )
        return

    from django.core.mail import EmailMultiAlternatives

    omitted = getattr(getattr(book, "build_job", None), "omitted_chapters", None) or []
    omitted_text, omitted_html = _omitted_email_sections(omitted)

    from_email = getattr(settings, "FROM_EMAIL", "noreply@openchapters.org")
    subject = f"Your book HTML is ready: {book.title}"
    text_body = (
        f"Hi,\n\n"
        f'Your book "{book.title}" has been typeset as HTML and is ready to read online.\n\n'
        f"View online: {view_url}\n"
        f"Download zip: {download_url}\n\n"
        f"{omitted_text}"
        f"— OpenChapters"
    )
    html_body = (
        f"<p>Hi,</p>"
        f'<p>Your book <strong>{book.title}</strong> has been typeset as HTML and is ready.</p>'
        f'<p><a href="{view_url}" style="display:inline-block;padding:12px 24px;'
        f'background-color:#2563eb;color:#ffffff;text-decoration:none;border-radius:6px;'
        f'font-weight:600;">Read online</a> &nbsp; '
        f'<a href="{download_url}" style="display:inline-block;padding:12px 24px;'
        f'background-color:#e5e7eb;color:#111827;text-decoration:none;border-radius:6px;'
        f'font-weight:600;">Download HTML (zip)</a></p>'
        f'<p><small>You can also access these from your '
        f'<a href="{site_url}/library">Library</a>.</small></p>'
        f"{omitted_html}"
        f"<p>— OpenChapters</p>"
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=f"OpenChapters <{from_email}>",
        to=[book.user.email],
    )
    msg.attach_alternative(html_body, "text/html")

    try:
        msg.send()
        logger.info("deliver_book_html: email sent to %s", book.user.email)
    except Exception as exc:
        logger.error(
            "deliver_book_html: SMTP error for book %d (attempt %d/%d): %s",
            book_id, self.request.retries + 1, 3, exc,
        )
        raise
