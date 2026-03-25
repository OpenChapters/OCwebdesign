"""
build_main_tex.py

Reads build_request.json from the temp build directory and renders
main.tex using the main.tex.j2 Jinja2 template.

Usage:
    python build_main_tex.py --workdir /tmp/ocbuild-<uuid> --build-id <uuid>

The script expects:
    <workdir>/build_request.json   — book assembly spec written by the web backend
    <script_dir>/main.tex.j2       — Jinja2 template (alongside this script)

It writes:
    <workdir>/main.tex             — ready for arara

build_request.json format:
{
    "book_title": "Introduction to Engineering Mathematics",
    "parts": [
        {
            "title": "Calculus",
            "chapters": [
                {
                    "repo": "OpenChapters/chapter-calc01",
                    "entry_file": "src/calc01.tex"
                }
            ]
        }
    ]
}

chapter.include_path is derived as:
    <repo-name-without-org>/<entry_file_without_extension>
    e.g. "chapter-calc01/src/calc01"
which is the path LaTeX's \\include{} expects, relative to main.tex.
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import jinja2


def repo_dirname(repo: str) -> str:
    """Return the local directory name for a cloned repo.

    "OpenChapters/chapter-calc01" -> "chapter-calc01"
    """
    return repo.split("/")[-1]


def include_path(repo: str, entry_file: str) -> str:
    """Return the LaTeX \\include{} path for a chapter.

    LaTeX's \\include{} takes a path relative to main.tex without the
    .tex extension.

    "OpenChapters/chapter-calc01", "src/calc01.tex"
        -> "chapter-calc01/src/calc01"
    """
    dirname = repo_dirname(repo)
    # Strip .tex extension
    entry = re.sub(r"\.tex$", "", entry_file)
    return f"{dirname}/{entry}"


def render(workdir: Path, build_id: str) -> None:
    request_path = workdir / "build_request.json"
    if not request_path.exists():
        raise FileNotFoundError(f"build_request.json not found in {workdir}")

    with open(request_path) as f:
        request = json.load(f)

    # Resolve chapter include paths
    parts = []
    for part in request["parts"]:
        chapters = []
        for ch in part["chapters"]:
            chapters.append(
                {
                    "repo": ch["repo"],
                    "entry_file": ch["entry_file"],
                    "include_path": include_path(ch["repo"], ch["entry_file"]),
                }
            )
        parts.append({"title": part["title"], "chapters": chapters})

    build_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Configure Jinja2 with LaTeX-safe delimiters (avoids conflicts with {})
    template_dir = Path(__file__).parent
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_dir)),
        block_start_string="(%",
        block_end_string="%)",
        variable_start_string="((",
        variable_end_string="))",
        comment_start_string="(#",
        comment_end_string="#)",
        keep_trailing_newline=True,
    )

    template = env.get_template("main.tex.j2")
    rendered = template.render(
        book_title=request["book_title"],
        parts=parts,
        build_id=build_id,
        build_date=build_date,
    )

    output_path = workdir / "main.tex"
    output_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render main.tex from build_request.json"
    )
    parser.add_argument("--workdir", required=True, help="Temp build directory path")
    parser.add_argument("--build-id", required=True, help="Build UUID")
    args = parser.parse_args()

    render(Path(args.workdir), args.build_id)


if __name__ == "__main__":
    main()
