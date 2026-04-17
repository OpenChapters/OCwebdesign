"""
Management command to build HTML output for published chapters using lwarp.

Usage:
    python manage.py build_chapter_html                    # all published
    python manage.py build_chapter_html --chabbr BASCRY    # single chapter
    python manage.py build_chapter_html --dry-run          # preview only
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
from django.utils import timezone

from catalog.models import Chapter

logger = logging.getLogger(__name__)

_SAFE_REPO = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
_SAFE_PATH = re.compile(r"^[a-zA-Z0-9_/.+-]+$")

# Directories
SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "Build" / "scripts"
TEMPLATE_HTML_DIR = Path(__file__).resolve().parents[3] / "Build" / "template_html"
TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "Build" / "template"
HTML_OUTPUT_DIR = Path(settings.BASE_DIR) / "media" / "html"


def _repo_dirname(repo: str) -> str:
    return repo.split("/")[-1]


def _include_path(repo: str, entry_file: str) -> str:
    dirname = _repo_dirname(repo)
    entry = re.sub(r"\.tex$", "", entry_file)
    return f"{dirname}/{entry}"


def _build_chapter_worker(data):
    """Standalone function for ProcessPoolExecutor (must be picklable).

    Receives serializable chapter data, sets up Django, and runs the build.
    """
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ocweb.settings.dev")
    django.setup()

    from catalog.models import Chapter
    ch_id = data[0]
    chapter = Chapter.objects.get(id=ch_id)
    cmd = Command()
    cmd.stdout = type("NullOut", (), {"write": lambda self, x: None, "flush": lambda self: None})()
    cmd._build_chapter(chapter)


class Command(BaseCommand):
    help = "Build HTML output for published chapters using lwarp"

    def add_arguments(self, parser):
        parser.add_argument("--chabbr", help="Build only this chapter (by chabbr)")
        parser.add_argument("--dry-run", action="store_true", help="Preview only")
        parser.add_argument(
            "--parallel", type=int, default=1, metavar="N",
            help="Build N chapters in parallel (default: 1, sequential)",
        )

    def handle(self, *args, **options):
        chabbr = options.get("chabbr")
        dry_run = options.get("dry_run", False)
        parallel = max(1, options.get("parallel", 1))

        chapters = Chapter.objects.filter(published=True)
        if chabbr:
            chapters = chapters.filter(chabbr=chabbr)

        if not chapters.exists():
            self.stdout.write(self.style.WARNING("No matching chapters found."))
            return

        # Filter to buildable chapters
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
                self.stdout.write(f"  [dry-run] Would build HTML for: {ch.title} ({ch.chabbr})")
            else:
                buildable.append(ch)

        if dry_run or not buildable:
            self.stdout.write(f"Skipped: {len(skipped)}")
            return

        if parallel > 1 and len(buildable) > 1:
            updated, errors = self._build_parallel(buildable, parallel)
        else:
            updated, errors = self._build_sequential(buildable)

        self.stdout.write("")
        self.stdout.write(f"Updated: {len(updated)}, Skipped: {len(skipped)}, Errors: {len(errors)}")
        for e in errors:
            self.stdout.write(self.style.ERROR(f"  {e}"))

    def _build_sequential(self, chapters):
        updated = []
        errors = []
        for ch in chapters:
            self.stdout.write(f"  Building HTML for: {ch.title} ({ch.chabbr})...")
            try:
                self._build_chapter(ch)
                updated.append(ch.title)
                self.stdout.write(self.style.SUCCESS(f"    OK"))
            except Exception as exc:
                errors.append(f"{ch.title}: {exc}")
                self.stdout.write(self.style.ERROR(f"    FAILED: {exc}"))
        return updated, errors

    def _build_parallel(self, chapters, max_workers):
        from concurrent.futures import ProcessPoolExecutor, as_completed

        updated = []
        errors = []

        self.stdout.write(f"  Building {len(chapters)} chapters with {max_workers} workers...")

        # Use ProcessPoolExecutor to avoid GIL; pass serializable data
        chapter_data = [
            (ch.id, ch.title, ch.chabbr, ch.github_repo, ch.chapter_subdir,
             ch.latex_entry_file, ch.authors, ch.description)
            for ch in chapters
        ]

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_build_chapter_worker, data): data
                for data in chapter_data
            }
            for future in as_completed(futures):
                data = futures[future]
                title, chabbr = data[1], data[2]
                try:
                    future.result()
                    updated.append(title)
                    self.stdout.write(self.style.SUCCESS(f"    OK: {title} ({chabbr})"))
                except Exception as exc:
                    errors.append(f"{title}: {exc}")
                    self.stdout.write(self.style.ERROR(f"    FAILED: {title} ({chabbr}): {exc}"))

        return updated, errors

    def _build_chapter(self, chapter: Chapter) -> None:
        build_id = str(uuid.uuid4())
        workdir = Path(f"/tmp/ochtml-{build_id}")
        workdir.mkdir(parents=True)

        try:
            self._setup_workspace(workdir, chapter)
            self._clone_repo(workdir, chapter)
            self._collect_images(workdir, chapter)
            self._convert_images_to_svg(workdir)
            self._copy_bib(workdir, chapter)
            self._render_templates(workdir, chapter)
            self._write_gin(workdir, build_id)
            self._run_arara(workdir)
            self._postprocess_html(workdir, chapter)
            self._collect_output(workdir, chapter)

            # Update the model
            chapter.html_built_at = timezone.now()
            chapter.save(update_fields=["html_built_at"])
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def _setup_workspace(self, workdir: Path, chapter: Chapter) -> None:
        """Copy HTML template files into the workspace."""
        # Copy HTML-specific templates
        for f in TEMPLATE_HTML_DIR.iterdir():
            if f.is_file():
                shutil.copy2(f, workdir / f.name)

        # Copy shared .sty files from the PDF template dir
        for sty_name in ("arara.sty", "mytodonotes.sty"):
            sty_path = TEMPLATE_DIR / sty_name
            if sty_path.exists():
                shutil.copy2(sty_path, workdir / sty_name)

        # Create ImageFolder
        (workdir / "ImageFolder").mkdir(exist_ok=True)

    def _clone_repo(self, workdir: Path, chapter: Chapter) -> None:
        """Shallow-clone the chapter's repository."""
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
        """Copy chapter figures into ImageFolder/."""
        repo_dir = workdir / _repo_dirname(chapter.github_repo)
        if chapter.chapter_subdir:
            content_dir = repo_dir / chapter.chapter_subdir
        else:
            content_dir = repo_dir

        image_dir = workdir / "ImageFolder"
        count = 0

        # Check pdf/ first, then eps/
        for subdir_name in ("pdf", "eps"):
            fig_dir = content_dir / subdir_name
            if fig_dir.is_dir():
                for f in fig_dir.iterdir():
                    if f.is_file():
                        shutil.copy2(f, image_dir / f.name)
                        count += 1

        # Also check chapter/ subdirectory pattern
        chapter_fig_dirs = [
            content_dir / "chapter" / "pdf",
            content_dir / "chapter" / "eps",
        ]
        for fig_dir in chapter_fig_dirs:
            if fig_dir.is_dir():
                for f in fig_dir.iterdir():
                    if f.is_file():
                        shutil.copy2(f, image_dir / f.name)
                        count += 1

        logger.info("Collected %d image files for %s", count, chapter.chabbr)

    def _convert_images_to_svg(self, workdir: Path) -> None:
        """Convert PDF figures in ImageFolder/ to SVG for lwarp HTML output."""
        image_dir = workdir / "ImageFolder"
        count = 0
        for pdf_file in list(image_dir.glob("*.pdf")):
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
                logger.warning("pdf2svg not installed; skipping SVG conversion")
                return
            except subprocess.CalledProcessError as e:
                logger.warning("pdf2svg failed for %s: %s", pdf_file.name, e.stderr)
            except subprocess.TimeoutExpired:
                logger.warning("pdf2svg timed out for %s", pdf_file.name)
        logger.info("Converted %d PDF figures to SVG", count)

    def _copy_bib(self, workdir: Path, chapter: Chapter) -> None:
        """Copy the chapter's bibliography file to the workspace root."""
        repo_dir = workdir / _repo_dirname(chapter.github_repo)
        if chapter.chapter_subdir:
            content_dir = repo_dir / chapter.chapter_subdir
        else:
            content_dir = repo_dir

        # Search for chaptercitations.bib in common locations
        candidates = [
            content_dir / "chaptercitations.bib",
            content_dir / "chapter" / "chaptercitations.bib",
        ]
        for bib_path in candidates:
            if bib_path.exists():
                shutil.copy2(bib_path, workdir / "chaptercitations.bib")
                return

        # If no bib file, create an empty one so biber doesn't fail
        (workdir / "chaptercitations.bib").write_text("", encoding="utf-8")
        logger.warning("No chaptercitations.bib found for %s", chapter.chabbr)

    def _render_templates(self, workdir: Path, chapter: Chapter) -> None:
        """Render the Jinja2 template to produce main.tex and main_html.tex."""
        import jinja2 as j2

        include = _include_path(chapter.github_repo, chapter.latex_entry_file)

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
        template = env.get_template("main_chapter_html.tex.j2")
        rendered = template.render(
            chapter_title=chapter.title,
            chabbr=chapter.chabbr,
            authors=", ".join(chapter.authors),
            description=chapter.description[:200] if chapter.description else "",
            include_path=include,
            build_date=timezone.now().strftime("%Y-%m-%d"),
        )

        (workdir / "main.tex").write_text(rendered, encoding="utf-8")

        # lwarp two-pass wrapper
        (workdir / "main_html.tex").write_text(
            "\\PassOptionsToPackage{warpHTML,BaseJobname=main}{lwarp}\n"
            "\\input{main.tex}\n",
            encoding="utf-8",
        )

    def _write_gin(self, workdir: Path, build_id: str) -> None:
        """Write a synthetic gitHeadLocal.gin for gitinfo2 compatibility."""
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
        """Run arara on main.tex to trigger the full lwarp build pipeline."""
        env = os.environ.copy()
        env["OCBUILD_SCRIPTS_DIR"] = str(SCRIPTS_DIR)
        # Ensure the wrapper scripts are findable
        env["PATH"] = "/usr/local/bin:" + env.get("PATH", "")

        result = subprocess.run(
            ["arara", "-v", "main.tex"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=1800,  # 30 min timeout per chapter
            env=env,
            stdin=subprocess.DEVNULL,  # prevent hang on LaTeX error prompts
        )

        if result.returncode != 0:
            # Try to extract useful error from the log
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

    def _postprocess_html(self, workdir: Path, chapter: Chapter) -> None:
        """Inject custom CSS into generated HTML files after lwarp build."""
        css_link = '<link rel="stylesheet" type="text/css" href="ocweb_overrides.css" />'
        cover_style = (
            f'<style>.sidetoctitle::before {{ '
            f'--oc-cover-image: url("ImageFolder/{chapter.chabbr}header.svg"); '
            f'}}</style>'
        )
        injection = f'{css_link}\n{cover_style}'

        for html_file in workdir.glob("*.html"):
            content = html_file.read_text(encoding="utf-8", errors="replace")
            # Insert before </head>
            if "</head>" in content:
                content = content.replace("</head>", f"{injection}\n</head>", 1)
                html_file.write_text(content, encoding="utf-8")

    def _collect_output(self, workdir: Path, chapter: Chapter) -> None:
        """Copy generated HTML and assets to the media directory."""
        HTML_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        output_dir = HTML_OUTPUT_DIR / chapter.chabbr
        # Atomic swap: write to temp, then rename
        tmp_dir = HTML_OUTPUT_DIR / f".tmp-{chapter.chabbr}-{uuid.uuid4().hex[:8]}"
        tmp_dir.mkdir(parents=True)

        try:
            # Copy HTML files
            for html_file in workdir.glob("*.html"):
                shutil.copy2(html_file, tmp_dir / html_file.name)

            # Copy CSS files
            for css_file in workdir.glob("*.css"):
                shutil.copy2(css_file, tmp_dir / css_file.name)

            # Copy SVG images from ImageFolder
            img_src = workdir / "ImageFolder"
            if img_src.is_dir():
                img_dest = tmp_dir / "ImageFolder"
                img_dest.mkdir()
                for svg_file in img_src.glob("*.svg"):
                    shutil.copy2(svg_file, img_dest / svg_file.name)
                # Also copy any PNG files generated by lwarp
                for png_file in img_src.glob("*.png"):
                    shutil.copy2(png_file, img_dest / png_file.name)

            # Copy MathJax config if present
            mathjax_txt = workdir / "lwarp_mathjax.txt"
            if mathjax_txt.exists():
                shutil.copy2(mathjax_txt, tmp_dir / mathjax_txt.name)

            # Verify we got at least an index.html
            if not (tmp_dir / "index.html").exists():
                raise RuntimeError("No index.html generated")

            # Atomic swap
            if output_dir.exists():
                shutil.rmtree(output_dir)
            tmp_dir.rename(output_dir)

        except Exception:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise
