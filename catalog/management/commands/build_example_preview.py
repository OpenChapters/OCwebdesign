"""
Management command to build a snippet preview for a worked Example.

Renders a minimal main.tex containing the example's statement and
solution, using the shared OpenChapters preamble. Runs arara, then
atomically writes the resulting PDF to media/examples/<id>.pdf and
updates the Example record's preview_built_at / preview_build_log.

Usage:
    python manage.py build_example_preview --id 17
"""

import logging
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from catalog.models import Example

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "Build" / "scripts"
TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "Build" / "template"
EXAMPLES_OUTPUT_DIR = Path(settings.BASE_DIR) / "media" / "examples"


class Command(BaseCommand):
    help = "Build a snippet preview PDF for a single Example."

    def add_arguments(self, parser):
        parser.add_argument(
            "--id",
            type=int,
            required=True,
            help="Primary key of the Example to build.",
        )

    def handle(self, *args, **options):
        example_id = options["id"]
        try:
            example = Example.objects.select_related("primary_chapter").get(pk=example_id)
        except Example.DoesNotExist:
            raise CommandError(f"Example {example_id} not found.")

        self.stdout.write(f"Building preview for Example #{example.id}…")
        try:
            self._build(example)
        except Exception as exc:
            log_excerpt = str(exc)[-8000:]
            example.preview_build_log = log_excerpt
            # Omit updated_at from update_fields — auto_now=True only fires
            # for listed fields, so this avoids invalidating the
            # preview-freshness gate on a build failure.
            example.save(update_fields=["preview_build_log"])
            self.stdout.write(self.style.ERROR(f"  FAILED: {exc}"))
            raise
        else:
            example.preview_built_at = timezone.now()
            example.preview_build_log = ""
            example.save(update_fields=["preview_built_at", "preview_build_log"])
            self.stdout.write(self.style.SUCCESS(f"  OK (media/examples/{example.id}.pdf)"))

    # ── Pipeline ─────────────────────────────────────────────────────────────

    def _build(self, example: Example) -> None:
        build_id = uuid.uuid4().hex
        workdir = Path(f"/tmp/ocexample-{build_id}")
        workdir.mkdir(parents=True)
        try:
            self._setup_workspace(workdir)
            self._render_template(workdir, example)
            self._run_arara(workdir)
            self._collect_output(workdir, example)
        except Exception:
            logger.warning("Build failed — workspace preserved at %s", workdir)
            raise
        else:
            shutil.rmtree(workdir, ignore_errors=True)

    def _setup_workspace(self, workdir: Path) -> None:
        for f in TEMPLATE_DIR.iterdir():
            if f.is_file():
                shutil.copy2(f, workdir / f.name)
        # Some macros reference graphics paths even when no images are
        # included. Create the directory so \graphicspath resolves.
        (workdir / "ImageFolder").mkdir(exist_ok=True)
        (workdir / ".latexmkrc").write_text(
            "$pdflatex = 'pdflatex -interaction=nonstopmode -halt-on-error "
            "--shell-escape %O %S';\n",
            encoding="utf-8",
        )

    def _render_template(self, workdir: Path, example: Example) -> None:
        import jinja2 as j2

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
        template = env.get_template("main_example.tex.j2")
        rendered = template.render(
            example_id=example.id,
            primary_chabbr=example.primary_chapter.chabbr or "—",
            statement_tex=example.statement_tex,
            solution_tex=example.solution_tex,
            build_date=timezone.now().strftime("%Y-%m-%d"),
        )
        (workdir / "main.tex").write_text(rendered, encoding="utf-8")

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
            timeout=90,  # snippets are short
            env=env,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            log_file = workdir / "main.log"
            error_tail = ""
            if log_file.exists():
                lines = log_file.read_text(errors="replace").splitlines()
                error_lines = [ln for ln in lines if ln.startswith("!")]
                error_tail = "\n".join(error_lines[:8]) if error_lines else ""
            raise RuntimeError(
                f"arara failed (exit {result.returncode})\n"
                f"stdout tail: {result.stdout[-1500:]}\n"
                f"stderr tail: {result.stderr[-500:]}\n"
                f"log errors: {error_tail}"
            )

    def _collect_output(self, workdir: Path, example: Example) -> None:
        EXAMPLES_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        src = workdir / "main.pdf"
        if not src.is_file():
            raise RuntimeError("No main.pdf produced.")
        dest = EXAMPLES_OUTPUT_DIR / f"{example.id}.pdf"
        tmp = EXAMPLES_OUTPUT_DIR / f".tmp-{example.id}-{uuid.uuid4().hex[:8]}.pdf"
        try:
            shutil.copy2(src, tmp)
            tmp.replace(dest)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
