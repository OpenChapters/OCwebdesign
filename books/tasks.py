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
import uuid
import zipfile
from pathlib import Path

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

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


def _build_request_data(book) -> dict:
    """Serialize a Book's chapter selection into the build_request.json schema.

    Automatically includes any foundational chapters that are listed in
    ``depends_on`` by the selected chapters but not already present in the
    book.  These are prepended as a "Foundations" part so that their
    ``\\label`` commands are available for cross-chapter ``\\ref`` resolution.
    """
    from catalog.models import Chapter

    parts = []
    included_chabbrs: set[str] = set()

    for part in book.parts.order_by("order"):
        chapters = []
        for bc in part.book_chapters.order_by("order").select_related("chapter"):
            ch = bc.chapter
            chapters.append({
                "repo": ch.github_repo,
                "chapter_subdir": ch.chapter_subdir,
                "entry_file": ch.latex_entry_file,
            })
            if ch.chabbr:
                included_chabbrs.add(ch.chabbr)
        parts.append({"title": part.title, "chapters": chapters})

    # Resolve foundational-chapter dependencies --------------------------
    # Collect all chabbr values referenced by depends_on across the book.
    all_chapters = Chapter.objects.filter(
        id__in=book.parts.values_list(
            "book_chapters__chapter_id", flat=True,
        )
    )
    needed_chabbrs: set[str] = set()
    for ch in all_chapters:
        for dep in ch.depends_on:
            if dep not in included_chabbrs:
                needed_chabbrs.add(dep)

    if needed_chabbrs:
        dep_chapters = (
            Chapter.objects.filter(chabbr__in=needed_chabbrs, published=True)
            .order_by("title")
        )
        dep_entries = []
        for ch in dep_chapters:
            dep_entries.append({
                "repo": ch.github_repo,
                "chapter_subdir": ch.chapter_subdir,
                "entry_file": ch.latex_entry_file,
            })
        if dep_entries:
            # Prepend a Foundations part so labels are defined before
            # they are referenced by topical chapters.
            parts.insert(0, {"title": "Foundations", "chapters": dep_entries})

    return {"book_title": book.title, "parts": parts}


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


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="books.build_book",
    time_limit=1800,       # hard kill after 30 min
    soft_time_limit=1500,  # SoftTimeLimitExceeded raised at 25 min
)
def build_book(self, book_id: int) -> None:
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
    job.save()

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
        # 1. Create workspace
        workdir.mkdir(parents=True, exist_ok=False)
        log(f"Workspace: {workdir}")

        # 2. Copy template files (.sty, .ins, .ist) into workspace root
        for f in template_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, workdir / f.name)
        log(f"Copied template files from {template_dir}")

        # 3. Write build_request.json
        request_data = _build_request_data(book)
        (workdir / "build_request.json").write_text(
            json.dumps(request_data, indent=2), encoding="utf-8"
        )
        log("Wrote build_request.json")

        # 3a. Validate all repo names and paths before subprocess calls
        _validate_build_data(request_data)
        log("Validated build request data")

        # 4. Clone chapter repo(s) — deduplicated; shallow clone for speed
        from catalog.git_provider import get_provider
        provider = get_provider()
        repos = {ch["repo"] for p in request_data["parts"] for ch in p["chapters"]}
        for repo in repos:
            repo_dir = workdir / repo.split("/")[-1]
            _run(
                ["git", "clone", "--depth=1", provider.clone_url(repo), str(repo_dir)],
                log,
            )

        # 5. Copy matter/ from the cloned monorepo into the workspace
        #    main.tex.j2 expects \input{matter/Frontmatter} relative to workdir.
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

        # 5a. Process Frontmatter.tex.template → Frontmatter.tex
        #     Replace ##COVERIMAGE##, ##BOOKTITLE##, ##USERNAME##
        fm_template = workdir / "matter" / "Frontmatter.tex.template"
        fm_output = workdir / "matter" / "Frontmatter.tex"
        if fm_template.is_file():
            cover_filename = "background.pdf"  # default
            if book.cover_image:
                cover_filename = Path(book.cover_image.name).name
            fm_text = fm_template.read_text()
            fm_text = fm_text.replace("##COVERIMAGE##", cover_filename)
            fm_text = fm_text.replace("##BOOKTITLE##", book.title)
            fm_text = fm_text.replace("##USERNAME##", book.user.full_name or book.user.email)
            fm_output.write_text(fm_text)
            log(f"Processed Frontmatter.tex (cover={cover_filename}, title={book.title}, user={book.user.full_name or book.user.email})")

        # 5b. Copy cover image to ImageFolder/
        img_folder = workdir / "ImageFolder"
        img_folder.mkdir(exist_ok=True)
        if book.cover_image:
            cover_src = Path(book.cover_image.path)
            if cover_src.is_file():
                shutil.copy2(str(cover_src), str(img_folder / Path(book.cover_image.name).name))
                log(f"Copied user cover image to ImageFolder/{Path(book.cover_image.name).name}")
        # Default background.pdf is already in matter/pdf/ which is on the graphics path

        # 6. Merge bibliography files → OpenChapters.bib
        _run_script(scripts_dir / "concat_bibs.py", workdir, log)

        # 7. Collect figures → ImageFolder/
        _run_script(scripts_dir / "collect_images.py", workdir, log)

        # 8. Render main.tex from Jinja2 template
        _run_script(
            scripts_dir / "build_main_tex.py", workdir, log,
            extra_args=["--build-id", build_id],
        )

        # 9. Write synthetic gitHeadLocal.gin (required by gitinfo2)
        _run_script(
            scripts_dir / "generate_gin.py", workdir, log,
            extra_args=["--build-id", build_id],
        )

        # 10. Run arara to typeset the PDF
        # -w enables whole-file directive scanning (the pre-7.0 default);
        # arara 7.x uses header-only mode by default which misses directives
        # that follow non-directive comment lines (e.g. % !TEX TS-program).
        try:
            _run(["arara", "-w", "main.tex"], log, cwd=workdir)
        except subprocess.CalledProcessError:
            # Capture the LaTeX log for diagnostics
            tex_log = workdir / "main.log"
            if tex_log.exists():
                log_text = tex_log.read_text(errors="replace")
                # Extract error lines (! prefix) and surrounding context
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
                    # No obvious error lines; show last 30 lines
                    log("--- Last 30 lines of main.log ---")
                    log("\n".join(lines[-30:]))
            raise

        # 11a. Verify PDF was produced
        pdf_src = workdir / "main.pdf"
        if not pdf_src.exists():
            raise FileNotFoundError(
                "arara completed without error but main.pdf was not found"
            )

        # 11b. Store PDF
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_filename = f"book_{book.id}_{build_id[:8]}.pdf"
        pdf_dst = output_dir / pdf_filename
        shutil.copy2(pdf_src, pdf_dst)
        log(f"PDF saved: {pdf_dst}")

        # 11c. Update job and book status
        job.pdf_path = str(pdf_dst)
        job.finished_at = timezone.now()
        job.log_output = "\n".join(log_lines)
        job.save()

        book.status = Book.Status.COMPLETE
        book.save(update_fields=["status"])
        log("Build complete.")

        # 12. Trigger email delivery
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

    from_email = getattr(settings, "FROM_EMAIL", "noreply@openchapters.org")
    subject = f"Your book is ready: {book.title}"
    text_body = (
        f"Hi,\n\n"
        f'Your book "{book.title}" has been typeset and is ready for download.\n\n'
        f"Download your PDF:\n{download_url}\n\n"
        f"This link expires in {expiry_days} days.\n\n"
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


def _postprocess_book_html(workdir: Path, log_fn) -> None:
    """Link the ocweb_overrides stylesheet + sidetoc JS into every HTML file.

    Both assets are referenced by external URL (not inlined) so the
    production CSP — which omits ``script-src 'unsafe-inline'`` — does
    not block them.
    """
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
def build_book_html(self, book_id: int) -> None:
    """
    Per-book HTML build pipeline via lwarp.

    Mirrors ``build_book`` but renders the HTML-specific Jinja2 template
    and collects lwarp output (HTML files + SVG assets) into
    ``<BUILD_HTML_OUTPUT_DIR>/book_<id>/``. A zip archive of that output
    is written alongside so it can be downloaded as a single file.
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
    job.save()

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
        # 1. Workspace
        workdir.mkdir(parents=True, exist_ok=False)
        log(f"Workspace: {workdir}")

        # 2. Copy HTML-specific templates first (OpenChaptersHTML.sty, CSS, etc.)
        for f in template_html_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, workdir / f.name)
        log(f"Copied HTML template files from {template_html_dir}")

        # Also copy supporting .sty files from the PDF template dir
        # (arara.sty, mytodonotes.sty). OpenChapters.sty / preamble.ins
        # are NOT copied — the HTML build uses the lwarp-safe variants.
        for sty_name in ("arara.sty", "mytodonotes.sty", "StyleInd.ist"):
            sty_path = template_dir / sty_name
            if sty_path.is_file():
                shutil.copy2(sty_path, workdir / sty_name)

        # Ensure latexmk invocations (including those from lwarpmk) run
        # non-interactively so the build never hangs on a pdflatex prompt.
        (workdir / ".latexmkrc").write_text(
            "$pdflatex = 'pdflatex -interaction=nonstopmode -halt-on-error "
            "--shell-escape %O %S';\n",
            encoding="utf-8",
        )

        # 3. Write build_request.json
        request_data = _build_request_data(book)
        (workdir / "build_request.json").write_text(
            json.dumps(request_data, indent=2), encoding="utf-8"
        )
        log("Wrote build_request.json")
        _validate_build_data(request_data)

        # 4. Clone chapter repo(s)
        from catalog.git_provider import get_provider
        provider = get_provider()
        repos = {ch["repo"] for p in request_data["parts"] for ch in p["chapters"]}
        for repo in repos:
            repo_dir = workdir / repo.split("/")[-1]
            _run(
                ["git", "clone", "--depth=1", provider.clone_url(repo), str(repo_dir)],
                log,
            )

        # 5. HTML builds skip matter/Frontmatter and matter/Postmatter —
        #    they rely on tikz-positioning, custom title-page commands
        #    (e.g. \OC, \chapterimage, \noheaderimage), and PDF-only
        #    graphics paths that lwarp can't render. The sidetoc +
        #    lwarp's own landing page replace the PDF front cover.
        img_folder = workdir / "ImageFolder"
        img_folder.mkdir(exist_ok=True)

        # 6. Merge bibs → OpenChapters.bib
        _run_script(scripts_dir / "concat_bibs.py", workdir, log)

        # 7. Collect figures into ImageFolder/
        _run_script(scripts_dir / "collect_images.py", workdir, log)

        # 7a. Convert PDF figures to SVG (required for lwarp HTML output)
        _convert_pdfs_to_svg(img_folder, log)

        # 8. Render main.tex + main_html.tex from Jinja2 template
        author = book.user.full_name or book.user.email
        _run_script(
            scripts_dir / "build_main_book_html_tex.py", workdir, log,
            extra_args=[
                "--build-id", build_id,
                "--book-author", author,
            ],
        )

        # 9. Write a lwarp-safe gitHeadLocal.gin for gitinfo2.
        #    generate_gin.py writes \usepackage[...]{gitexinfo}, which
        #    lwarp rejects (it refuses braces in package options). We
        #    use the same \renewcommand style that build_chapter_html
        #    uses for its HTML builds.
        _write_html_gin(workdir, build_id)

        # 10. Run arara — triggers the full lwarp chain
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

        # 10a. Verify lwarp produced the expected HTML landing page
        index_html = workdir / "index.html"
        if not index_html.exists():
            raise FileNotFoundError("arara completed but index.html was not generated")

        # 11. Post-process the HTML (inject ocweb_overrides.css)
        _postprocess_book_html(workdir, log)

        # 12. Collect output → <html_output_root>/book_<id>/
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

            mathjax_txt = workdir / "lwarp_mathjax.txt"
            if mathjax_txt.exists():
                shutil.copy2(mathjax_txt, tmp_dir / mathjax_txt.name)

            if not (tmp_dir / "index.html").exists():
                raise RuntimeError("No index.html was copied to output")

            # 12a. Pre-build the zip archive so downloads are O(1) rather
            # than re-zipped per request. Write the archive to a location
            # OUTSIDE tmp_dir first so os.walk doesn't capture the
            # archive mid-write, then move it in.
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

        # 13. Update Book + BuildJob
        book.html_path = str(output_dir)
        book.html_built_at = timezone.now()
        book.status = Book.Status.COMPLETE
        book.save(update_fields=["html_path", "html_built_at", "status"])

        job.finished_at = timezone.now()
        job.log_output = "\n".join(log_lines)
        job.save()

        log("HTML build complete.")

        # 14. Email the user a link to view / download the HTML output
        deliver_book_html.delay(book.id)

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

    site_url = getattr(settings, "SITE_URL", "http://localhost:5173").rstrip("/")
    view_url = f"{site_url}/books/{book.id}/read"
    download_url = f"{site_url}/api/books/{book.id}/download-html/"

    if not getattr(settings, "EMAIL_HOST", ""):
        logger.info(
            "deliver_book_html: EMAIL_HOST not set; would email %s: %s",
            book.user.email, view_url,
        )
        return

    from django.core.mail import EmailMultiAlternatives

    from_email = getattr(settings, "FROM_EMAIL", "noreply@openchapters.org")
    subject = f"Your book HTML is ready: {book.title}"
    text_body = (
        f"Hi,\n\n"
        f'Your book "{book.title}" has been typeset as HTML and is ready to read online.\n\n'
        f"View online: {view_url}\n"
        f"Download zip: {download_url}\n\n"
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
