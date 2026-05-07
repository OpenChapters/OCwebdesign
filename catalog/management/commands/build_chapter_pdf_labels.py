"""
Management command to build per-chapter labels-PDF for foundational chapters.

The output is the chapter typeset on its own (no Frontmatter/Postmatter)
with showkeys enabled, so prospective authors can see the existing
label scheme (sections, equations, figures, tables) for cross-referencing.

Usage:
    python manage.py build_chapter_pdf_labels                 # all foundational
    python manage.py build_chapter_pdf_labels --chabbr NUMSYS # single chapter
    python manage.py build_chapter_pdf_labels --dry-run       # preview only
"""

import logging
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from catalog.models import Chapter

logger = logging.getLogger(__name__)

_SAFE_REPO = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
_SAFE_PATH = re.compile(r"^[a-zA-Z0-9_/.+-]+$")

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "Build" / "scripts"
TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "Build" / "template"
PDF_LABELS_OUTPUT_DIR = Path(settings.BASE_DIR) / "media" / "pdf_labels"


def _repo_dirname(repo: str) -> str:
    return repo.split("/")[-1]


def _include_path(repo: str, entry_file: str) -> str:
    dirname = _repo_dirname(repo)
    entry = re.sub(r"\.tex$", "", entry_file)
    return f"{dirname}/{entry}"


class Command(BaseCommand):
    help = "Build per-chapter labels-PDF for foundational chapters"

    def add_arguments(self, parser):
        parser.add_argument(
            "--chabbr",
            help="Build only this chapter (by chabbr); bypasses the foundational filter",
        )
        parser.add_argument("--dry-run", action="store_true", help="Preview only")

    def handle(self, *args, **options):
        chabbr = options.get("chabbr")
        dry_run = options.get("dry_run", False)

        chapters = Chapter.objects.filter(published=True)
        if chabbr:
            chapters = chapters.filter(chabbr=chabbr)
        else:
            chapters = chapters.filter(
                chapter_type=Chapter.ChapterType.FOUNDATIONAL,
            )

        if not chapters.exists():
            self.stdout.write(self.style.WARNING("No matching chapters found."))
            return

        buildable = []
        skipped = []
        for ch in chapters:
            if not ch.chabbr:
                skipped.append(f"{ch.title}: no chabbr")
            elif not ch.github_repo or not _SAFE_REPO.match(ch.github_repo):
                skipped.append(f"{ch.title}: invalid github_repo")
            elif not ch.latex_entry_file or not _SAFE_PATH.match(ch.latex_entry_file):
                skipped.append(f"{ch.title}: invalid latex_entry_file")
            elif dry_run:
                self.stdout.write(
                    f"  [dry-run] Would build labels-PDF for: {ch.title} ({ch.chabbr})"
                )
            else:
                buildable.append(ch)

        if dry_run or not buildable:
            self.stdout.write(f"Skipped: {len(skipped)}")
            return

        updated = []
        errors = []
        for ch in buildable:
            self.stdout.write(f"  Building labels-PDF for: {ch.title} ({ch.chabbr})...")
            try:
                self._build_chapter(ch)
                updated.append(ch.title)
                self.stdout.write(self.style.SUCCESS("    OK"))
            except Exception as exc:
                errors.append(f"{ch.title}: {exc}")
                self.stdout.write(self.style.ERROR(f"    FAILED: {exc}"))

        self.stdout.write("")
        self.stdout.write(
            f"Updated: {len(updated)}, Skipped: {len(skipped)}, Errors: {len(errors)}"
        )
        for e in errors:
            self.stdout.write(self.style.ERROR(f"  {e}"))

    def _build_chapter(self, chapter: Chapter) -> None:
        build_id = str(uuid.uuid4())
        workdir = Path(f"/tmp/ocpdflabels-{build_id}")
        workdir.mkdir(parents=True)

        try:
            self._setup_workspace(workdir)
            self._clone_repo(workdir, chapter)
            self._collect_images(workdir, chapter)
            self._copy_bib(workdir, chapter)
            self._render_template(workdir, chapter)
            self._write_gin(workdir, build_id)
            self._run_arara(workdir)
            self._collect_output(workdir, chapter)
        except Exception:
            logger.warning("Build failed — workspace preserved at %s", workdir)
            raise
        else:
            shutil.rmtree(workdir, ignore_errors=True)

    def _setup_workspace(self, workdir: Path) -> None:
        for f in TEMPLATE_DIR.iterdir():
            if f.is_file():
                shutil.copy2(f, workdir / f.name)
        (workdir / "ImageFolder").mkdir(exist_ok=True)
        (workdir / ".latexmkrc").write_text(
            "$pdflatex = 'pdflatex -interaction=nonstopmode -halt-on-error "
            "--shell-escape %O %S';\n",
            encoding="utf-8",
        )

    def _clone_repo(self, workdir: Path, chapter: Chapter) -> None:
        repo = chapter.github_repo
        token = getattr(settings, "GITHUB_TOKEN", "") or getattr(settings, "GIT_TOKEN", "")
        if token:
            clone_url = f"https://x-access-token:{token}@github.com/{repo}.git"
        else:
            clone_url = f"https://github.com/{repo}.git"
        dest = workdir / _repo_dirname(repo)
        subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch", clone_url, str(dest)],
            capture_output=True,
            check=True,
            timeout=120,
        )

    def _collect_images(self, workdir: Path, chapter: Chapter) -> None:
        repo_dir = workdir / _repo_dirname(chapter.github_repo)
        if chapter.chapter_subdir:
            content_dir = repo_dir / chapter.chapter_subdir
        else:
            content_dir = repo_dir

        image_dir = workdir / "ImageFolder"
        count = 0
        for subdir_name in ("pdf", "eps"):
            fig_dir = content_dir / subdir_name
            if fig_dir.is_dir():
                for f in fig_dir.iterdir():
                    if f.is_file():
                        shutil.copy2(f, image_dir / f.name)
                        count += 1
        for fig_dir in (content_dir / "chapter" / "pdf", content_dir / "chapter" / "eps"):
            if fig_dir.is_dir():
                for f in fig_dir.iterdir():
                    if f.is_file():
                        shutil.copy2(f, image_dir / f.name)
                        count += 1
        logger.info("Collected %d image files for %s", count, chapter.chabbr)

    def _copy_bib(self, workdir: Path, chapter: Chapter) -> None:
        repo_dir = workdir / _repo_dirname(chapter.github_repo)
        if chapter.chapter_subdir:
            content_dir = repo_dir / chapter.chapter_subdir
        else:
            content_dir = repo_dir
        for bib_path in (
            content_dir / "chaptercitations.bib",
            content_dir / "chapter" / "chaptercitations.bib",
        ):
            if bib_path.exists():
                shutil.copy2(bib_path, workdir / "chaptercitations.bib")
                return
        (workdir / "chaptercitations.bib").write_text("", encoding="utf-8")
        logger.warning("No chaptercitations.bib found for %s", chapter.chabbr)

    def _render_template(self, workdir: Path, chapter: Chapter) -> None:
        import jinja2 as j2
        from django.utils import timezone

        env = j2.Environment(
            loader=j2.FileSystemLoader(str(SCRIPTS_DIR)),
            block_start_string="(%",
            block_end_string="%)",
            variable_start_string="((",
            variable_end_string="))",
            comment_start_string="(#",
            comment_end_string="#)",
            keep_trailing_newline=True,
        )
        template = env.get_template("main_chapter_labels.tex.j2")
        rendered = template.render(
            chapter_title=chapter.title,
            chabbr=chapter.chabbr,
            include_path=_include_path(chapter.github_repo, chapter.latex_entry_file),
            build_date=timezone.now().strftime("%Y-%m-%d"),
        )
        (workdir / "main.tex").write_text(rendered, encoding="utf-8")

    def _write_gin(self, workdir: Path, build_id: str) -> None:
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

    def _run_arara(self, workdir: Path) -> None:
        env = os.environ.copy()
        env["OCBUILD_SCRIPTS_DIR"] = str(SCRIPTS_DIR)
        env["PATH"] = "/usr/local/bin:" + env.get("PATH", "")
        par_cache = workdir / ".par_cache"
        par_cache.mkdir(exist_ok=True)
        env["PAR_GLOBAL_TEMP"] = str(par_cache)
        env["PAR_TEMP"] = str(par_cache)
        env["TMPDIR"] = str(par_cache)

        result = subprocess.run(
            ["arara", "-v", "main.tex"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=900,  # labels-PDF builds skip lwarp, so 15 min is plenty
            env=env,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            log_file = workdir / "main.log"
            error_tail = ""
            if log_file.exists():
                lines = log_file.read_text(errors="replace").splitlines()
                error_lines = [l for l in lines if l.startswith("!")]
                error_tail = "\n".join(error_lines[:5]) if error_lines else ""
            raise RuntimeError(
                f"arara failed (exit {result.returncode})\n"
                f"stdout: {result.stdout[-1000:]}\n"
                f"stderr: {result.stderr[-500:]}\n"
                f"log errors: {error_tail}"
            )

    def _collect_output(self, workdir: Path, chapter: Chapter) -> None:
        PDF_LABELS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        src = workdir / "main.pdf"
        if not src.is_file():
            raise RuntimeError("No main.pdf produced")
        dest = PDF_LABELS_OUTPUT_DIR / f"{chapter.chabbr}.pdf"
        # Atomic write: copy to temp in the same directory, then rename
        tmp = PDF_LABELS_OUTPUT_DIR / f".tmp-{chapter.chabbr}-{uuid.uuid4().hex[:8]}.pdf"
        try:
            shutil.copy2(src, tmp)
            tmp.replace(dest)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
