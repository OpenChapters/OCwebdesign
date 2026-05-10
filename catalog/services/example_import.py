"""
Batch importer for worked examples.

Accepts a zip file with this layout:

    batch.zip
    ├── manifest.json
    └── <dir>/
        ├── statement.tex
        ├── solution.tex
        └── figures/         (optional)
            ├── fig1.pdf
            └── fig2.png

`manifest.json` is a list of entries:

    [
      {
        "dir": "ex001",                    # required: directory name in zip
        "slug": "intro-rotation",          # optional: per-author idempotency key
        "primary_chapter": "BASCRY",       # required: chabbr
        "chapters": ["BASCRY", "DIFCAL"],  # required: list of chabbrs
        "difficulty": "standard"           # optional: defaults to standard
      },
      ...
    ]

Validation is staged into a parser pass (returning a structured report)
and a separate commit pass that mutates the DB. The commit re-validates
within a single transaction so a stale upload can't half-create.

The parser is intentionally role-agnostic: callers pass `default_author`
and `default_status`. The view is responsible for enforcing what those
can be (e.g. authors should be locked to DRAFT).
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Iterable

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from catalog.models import Chapter, Example, ExampleFigure


# ── Caps and allowed extensions ─────────────────────────────────────────

ZIP_TOTAL_BYTES_CAP = 50 * 1024 * 1024
FIGURE_MAX_BYTES = ExampleFigure.MAX_BYTES
FIGURE_ALLOWED_EXTENSIONS = ExampleFigure.ALLOWED_EXTENSIONS

MAX_ENTRIES_PER_BATCH = 200


# ── Report structures ──────────────────────────────────────────────────

@dataclass
class FigurePlan:
    original_filename: str
    bytes_data: bytes


@dataclass
class EntryPlan:
    """One example planned for create or update.

    `errors` is non-empty when this entry can't be persisted. `action`
    is "create" / "update" / "skip" — the latter only used when errors
    exist and we want the row to surface in the report anyway.
    """
    dir_name: str
    slug: str | None
    primary_chapter_chabbr: str
    chapters_chabbrs: list[str]
    difficulty: str
    statement_tex: str = ""
    solution_tex: str = ""
    figures: list[FigurePlan] = field(default_factory=list)
    action: str = "create"  # create | update | skip
    matched_example_id: int | None = None
    errors: list[str] = field(default_factory=list)
    # Filled in after a successful commit.
    persisted_id: int | None = None


@dataclass
class ImportReport:
    entries: list[EntryPlan] = field(default_factory=list)
    global_errors: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.global_errors) or any(e.errors for e in self.entries)

    @property
    def created_count(self) -> int:
        return sum(1 for e in self.entries if e.action == "create" and not e.errors)

    @property
    def updated_count(self) -> int:
        return sum(1 for e in self.entries if e.action == "update" and not e.errors)

    @property
    def error_count(self) -> int:
        return sum(1 for e in self.entries if e.errors) + len(self.global_errors)


# ── Parser ─────────────────────────────────────────────────────────────

def _safe_zip_path(name: str) -> PurePosixPath | None:
    """Return a normalized PurePosixPath if `name` is a safe relative
    path inside the zip, else None. Rejects absolute paths and any
    component traversing parent directories (zip-slip).
    """
    p = PurePosixPath(name)
    if p.is_absolute():
        return None
    if any(part in ("..", "") for part in p.parts):
        return None
    return p


def parse_zip(
    *,
    zip_bytes: bytes,
    default_author,
) -> ImportReport:
    """Parse and validate a batch zip without writing to the DB.

    `default_author` scopes the slug-match lookup so that re-imports by
    the same staff member find their own previously-imported rows.
    """
    report = ImportReport()

    if len(zip_bytes) > ZIP_TOTAL_BYTES_CAP:
        cap_mb = ZIP_TOTAL_BYTES_CAP // (1024 * 1024)
        report.global_errors.append(
            f"Zip exceeds the {cap_mb} MB cap "
            f"(uploaded {len(zip_bytes) / (1024 * 1024):.1f} MB)."
        )
        return report

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        report.global_errors.append("File is not a valid zip archive.")
        return report

    # Build a name → ZipInfo map keyed by safe paths only.
    safe_members: dict[str, zipfile.ZipInfo] = {}
    for info in zf.infolist():
        if info.is_dir():
            continue
        safe = _safe_zip_path(info.filename)
        if safe is None:
            report.global_errors.append(
                f"Refusing unsafe path in zip: {info.filename!r}"
            )
            continue
        safe_members[str(safe)] = info

    if report.global_errors:
        return report

    if "manifest.json" not in safe_members:
        report.global_errors.append("manifest.json is missing from the zip root.")
        return report

    try:
        manifest_text = zf.read(safe_members["manifest.json"]).decode("utf-8")
        manifest = json.loads(manifest_text)
    except UnicodeDecodeError:
        report.global_errors.append("manifest.json is not valid UTF-8.")
        return report
    except json.JSONDecodeError as e:
        report.global_errors.append(f"manifest.json is not valid JSON: {e}")
        return report

    if not isinstance(manifest, list):
        report.global_errors.append("manifest.json must be a JSON list of entries.")
        return report

    if len(manifest) == 0:
        report.global_errors.append("manifest.json contains no entries.")
        return report

    if len(manifest) > MAX_ENTRIES_PER_BATCH:
        report.global_errors.append(
            f"manifest.json has {len(manifest)} entries; cap is {MAX_ENTRIES_PER_BATCH}."
        )
        return report

    # Pre-resolve all chapters once for cheap chabbr → instance lookups.
    chabbr_set: set[str] = set()
    for entry in manifest:
        if isinstance(entry, dict):
            pc = entry.get("primary_chapter")
            if isinstance(pc, str):
                chabbr_set.add(pc)
            chs = entry.get("chapters") or []
            if isinstance(chs, list):
                for ch in chs:
                    if isinstance(ch, str):
                        chabbr_set.add(ch)
    chapter_by_chabbr: dict[str, Chapter] = {
        c.chabbr: c
        for c in Chapter.objects.filter(chabbr__in=chabbr_set, published=True)
    }

    # Slug deduplication within the manifest itself — two entries with
    # the same slug would silently overwrite each other on commit.
    seen_slugs: dict[str, int] = {}

    for idx, raw in enumerate(manifest, start=1):
        plan = _parse_entry(
            idx=idx,
            raw=raw,
            zf=zf,
            safe_members=safe_members,
            chapter_by_chabbr=chapter_by_chabbr,
            default_author=default_author,
            seen_slugs=seen_slugs,
        )
        report.entries.append(plan)

    return report


def _parse_entry(
    *,
    idx: int,
    raw,
    zf: zipfile.ZipFile,
    safe_members: dict[str, zipfile.ZipInfo],
    chapter_by_chabbr: dict[str, Chapter],
    default_author,
    seen_slugs: dict[str, int],
) -> EntryPlan:
    plan = EntryPlan(
        dir_name=f"(entry {idx})",
        slug=None,
        primary_chapter_chabbr="",
        chapters_chabbrs=[],
        difficulty="standard",
    )

    if not isinstance(raw, dict):
        plan.errors.append(f"Entry {idx} is not an object.")
        plan.action = "skip"
        return plan

    dir_name = raw.get("dir")
    if not isinstance(dir_name, str) or not dir_name.strip():
        plan.errors.append("`dir` is required and must be a non-empty string.")
        plan.action = "skip"
        return plan
    plan.dir_name = dir_name.strip()

    slug = raw.get("slug")
    if slug is not None:
        if not isinstance(slug, str) or not slug.strip():
            plan.errors.append("`slug` must be a non-empty string when provided.")
        elif len(slug) > 64:
            plan.errors.append("`slug` exceeds the 64-character cap.")
        else:
            plan.slug = slug.strip()
            if plan.slug in seen_slugs:
                plan.errors.append(
                    f"Duplicate slug {plan.slug!r} also used by entry {seen_slugs[plan.slug]}."
                )
            else:
                seen_slugs[plan.slug] = idx

    primary = raw.get("primary_chapter")
    if not isinstance(primary, str) or not primary.strip():
        plan.errors.append("`primary_chapter` is required and must be a chabbr string.")
    else:
        plan.primary_chapter_chabbr = primary.strip()
        if plan.primary_chapter_chabbr not in chapter_by_chabbr:
            plan.errors.append(
                f"Primary chapter chabbr {plan.primary_chapter_chabbr!r} not found "
                f"or unpublished."
            )

    chapters_raw = raw.get("chapters") or []
    if not isinstance(chapters_raw, list) or not chapters_raw:
        plan.errors.append("`chapters` is required and must be a non-empty list of chabbrs.")
    else:
        for ch in chapters_raw:
            if not isinstance(ch, str) or not ch.strip():
                plan.errors.append("Each chapter chabbr must be a non-empty string.")
                continue
            plan.chapters_chabbrs.append(ch.strip())
        unknown = [c for c in plan.chapters_chabbrs if c not in chapter_by_chabbr]
        if unknown:
            plan.errors.append(
                f"Unknown chapter chabbr(s): {', '.join(sorted(set(unknown)))}."
            )
        if (
            plan.primary_chapter_chabbr
            and plan.primary_chapter_chabbr not in plan.chapters_chabbrs
        ):
            plan.errors.append("`primary_chapter` must be one of the entries in `chapters`.")

    difficulty = raw.get("difficulty", "standard")
    if difficulty not in dict(Example.Difficulty.choices):
        plan.errors.append(
            f"`difficulty` must be one of: "
            f"{', '.join(c[0] for c in Example.Difficulty.choices)}."
        )
    else:
        plan.difficulty = difficulty

    statement_path = f"{plan.dir_name}/statement.tex"
    solution_path = f"{plan.dir_name}/solution.tex"

    if statement_path not in safe_members:
        plan.errors.append(f"Missing {statement_path}.")
    else:
        try:
            plan.statement_tex = zf.read(safe_members[statement_path]).decode("utf-8")
        except UnicodeDecodeError:
            plan.errors.append(f"{statement_path} is not valid UTF-8.")
        else:
            if not plan.statement_tex.strip():
                plan.errors.append(f"{statement_path} is empty.")

    if solution_path not in safe_members:
        plan.errors.append(f"Missing {solution_path}.")
    else:
        try:
            plan.solution_tex = zf.read(safe_members[solution_path]).decode("utf-8")
        except UnicodeDecodeError:
            plan.errors.append(f"{solution_path} is not valid UTF-8.")
        else:
            if not plan.solution_tex.strip():
                plan.errors.append(f"{solution_path} is empty.")

    figure_prefix = f"{plan.dir_name}/figures/"
    figure_basenames: set[str] = set()
    for member_path, info in safe_members.items():
        if not member_path.startswith(figure_prefix):
            continue
        rel = member_path[len(figure_prefix):]
        # No nested dirs under figures/ — keeps the basename-only
        # \includegraphics convention enforceable.
        if "/" in rel:
            plan.errors.append(
                f"Nested directory under {figure_prefix} not allowed: {rel}."
            )
            continue
        ext = ("." + rel.rsplit(".", 1)[-1].lower()) if "." in rel else ""
        if ext not in FIGURE_ALLOWED_EXTENSIONS:
            plan.errors.append(
                f"Figure {rel}: unsupported extension. "
                f"Allowed: {', '.join(FIGURE_ALLOWED_EXTENSIONS)}."
            )
            continue
        if rel in figure_basenames:
            plan.errors.append(f"Duplicate figure filename in {plan.dir_name}: {rel}.")
            continue
        figure_basenames.add(rel)
        if info.file_size > FIGURE_MAX_BYTES:
            cap_mb = FIGURE_MAX_BYTES // (1024 * 1024)
            plan.errors.append(
                f"Figure {rel} exceeds the {cap_mb} MB cap "
                f"({info.file_size / (1024 * 1024):.1f} MB)."
            )
            continue
        plan.figures.append(
            FigurePlan(
                original_filename=rel,
                bytes_data=zf.read(info),
            )
        )

    # Existing-row lookup for idempotency.
    if plan.slug:
        existing = (
            Example.objects
            .filter(author=default_author, slug=plan.slug)
            .first()
        )
        if existing is not None:
            plan.action = "update"
            plan.matched_example_id = existing.id
        else:
            plan.action = "create"
    else:
        plan.action = "create"

    if plan.errors:
        plan.action = "skip"

    return plan


# ── Commit ─────────────────────────────────────────────────────────────

def commit_report(
    *,
    report: ImportReport,
    default_author,
    default_status: str,
) -> ImportReport:
    """Persist the planned entries inside a single transaction.

    Re-checks `report.has_errors` first; refuses to write anything when
    the report is dirty. Figures are replaced wholesale on update.
    """
    if report.has_errors:
        # Preserve the report shape so the caller can surface what failed.
        return report

    if default_status not in dict(Example.Status.choices):
        report.global_errors.append(
            f"`default_status` must be one of: "
            f"{', '.join(c[0] for c in Example.Status.choices)}."
        )
        return report

    chabbrs_needed: set[str] = set()
    for plan in report.entries:
        chabbrs_needed.add(plan.primary_chapter_chabbr)
        chabbrs_needed.update(plan.chapters_chabbrs)
    chapter_by_chabbr = {
        c.chabbr: c
        for c in Chapter.objects.filter(chabbr__in=chabbrs_needed)
    }

    with transaction.atomic():
        for plan in report.entries:
            primary = chapter_by_chabbr[plan.primary_chapter_chabbr]
            chapters = [chapter_by_chabbr[c] for c in plan.chapters_chabbrs]

            if plan.action == "update" and plan.matched_example_id is not None:
                ex = Example.objects.select_for_update().get(pk=plan.matched_example_id)
                ex.primary_chapter = primary
                ex.statement_tex = plan.statement_tex
                ex.solution_tex = plan.solution_tex
                ex.difficulty = plan.difficulty
                # status is intentionally not changed on update.
                ex.preview_built_at = None
                ex.preview_build_log = ""
                ex.save()
                ex.chapters.set(chapters)

                # Replace figures wholesale.
                for old_fig in ex.figures.all():
                    try:
                        old_fig.file.delete(save=False)
                    except Exception:
                        pass
                ex.figures.all().delete()

            else:  # create
                ex = Example.objects.create(
                    author=default_author,
                    slug=plan.slug,
                    primary_chapter=primary,
                    statement_tex=plan.statement_tex,
                    solution_tex=plan.solution_tex,
                    difficulty=plan.difficulty,
                    status=default_status,
                )
                ex.chapters.set(chapters)

            for fig_plan in plan.figures:
                ExampleFigure.objects.create(
                    example=ex,
                    file=ContentFile(fig_plan.bytes_data, name=fig_plan.original_filename),
                    original_filename=fig_plan.original_filename,
                    order=0,
                )

            plan.persisted_id = ex.id

    return report


def report_to_dict(report: ImportReport) -> dict:
    """JSON-serializable shape for the API response."""
    return {
        "global_errors": list(report.global_errors),
        "summary": {
            "total": len(report.entries),
            "create": report.created_count,
            "update": report.updated_count,
            "errors": report.error_count,
        },
        "entries": [
            {
                "dir": e.dir_name,
                "slug": e.slug,
                "primary_chapter": e.primary_chapter_chabbr,
                "chapters": list(e.chapters_chabbrs),
                "difficulty": e.difficulty,
                "figure_count": len(e.figures),
                "action": e.action,
                "matched_example_id": e.matched_example_id,
                "persisted_id": e.persisted_id,
                "errors": list(e.errors),
            }
            for e in report.entries
        ],
    }
