"""
Celery tasks for the books app.

build_book  — full LaTeX build pipeline for a user's book assembly
deliver_pdf — email the completed PDF link to the user (stub; SendGrid TBD)
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from celery import shared_task
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
    """Serialize a Book's chapter selection into the build_request.json schema."""
    parts = []
    for part in book.parts.order_by("order"):
        chapters = []
        for bc in part.book_chapters.order_by("order").select_related("chapter"):
            ch = bc.chapter
            chapters.append({
                "repo": ch.github_repo,
                "chapter_subdir": ch.chapter_subdir,
                "entry_file": ch.latex_entry_file,
            })
        parts.append({"title": part.title, "chapters": chapters})
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
        repos = {ch["repo"] for p in request_data["parts"] for ch in p["chapters"]}
        for repo in repos:
            repo_dir = workdir / repo.split("/")[-1]
            _run(
                ["git", "clone", "--depth=1", f"https://github.com/{repo}.git", str(repo_dir)],
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

    Uses SendGrid if SENDGRID_API_KEY is configured; otherwise logs only.
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

    api_key = getattr(settings, "SENDGRID_API_KEY", "")
    if not api_key:
        logger.info(
            "deliver_pdf: SENDGRID_API_KEY not set; would email %s download link %s",
            book.user.email,
            download_url,
        )
        return

    from_email = getattr(settings, "FROM_EMAIL", "noreply@openchapters.org")

    import sendgrid
    from sendgrid.helpers.mail import Content, Email, Mail, To

    sg = sendgrid.SendGridAPIClient(api_key=api_key)
    mail = Mail(
        from_email=Email(from_email, "OpenChapters"),
        to_emails=To(book.user.email),
        subject=f"Your book is ready: {book.title}",
        plain_text_content=Content(
            "text/plain",
            f"Hi,\n\n"
            f'Your book "{book.title}" has been typeset and is ready for download.\n\n'
            f"Download your PDF:\n{download_url}\n\n"
            f"This link expires in {expiry_days} days.\n\n"
            f"— OpenChapters",
        ),
    )
    mail.add_content(
        Content(
            "text/html",
            f"<p>Hi,</p>"
            f'<p>Your book <strong>{book.title}</strong> has been typeset and is ready for download.</p>'
            f'<p><a href="{download_url}" style="display:inline-block;padding:12px 24px;'
            f"background-color:#2563eb;color:#ffffff;text-decoration:none;border-radius:6px;"
            f'font-weight:600;">Download PDF</a></p>'
            f"<p><small>This link expires in {expiry_days} days. "
            f"You can also download from your <a href=\"{site_url}/library\">Library</a>.</small></p>"
            f"<p>— OpenChapters</p>",
        ),
    )

    try:
        response = sg.client.mail.send.post(request_body=mail.get())
        logger.info(
            "deliver_pdf: email sent to %s (status %s)",
            book.user.email,
            response.status_code,
        )
    except Exception as exc:
        logger.error(
            "deliver_pdf: SendGrid error for book %d (attempt %d/%d): %s",
            book_id, self.request.retries + 1, 3, exc,
        )
        raise  # triggers autoretry
