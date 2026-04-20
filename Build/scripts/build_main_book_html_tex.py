"""
build_main_book_html_tex.py

Reads build_request.json from the temp build directory and renders
main.tex using the main_book_html.tex.j2 Jinja2 template, for per-book
HTML builds (lwarp).

Usage:
    python build_main_book_html_tex.py --workdir /tmp/ocbuild-<uuid> \\
        --build-id <uuid> --book-author "Author Name"

The script expects:
    <workdir>/build_request.json
    <script_dir>/main_book_html.tex.j2

It writes:
    <workdir>/main.tex
    <workdir>/main_html.tex     (lwarp two-pass wrapper)
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import jinja2


def repo_dirname(repo: str) -> str:
    return repo.split("/")[-1]


def include_path(repo: str, entry_file: str) -> str:
    dirname = repo_dirname(repo)
    entry = re.sub(r"\.tex$", "", entry_file)
    return f"{dirname}/{entry}"


def render(workdir: Path, build_id: str, book_author: str) -> None:
    request_path = workdir / "build_request.json"
    if not request_path.exists():
        raise FileNotFoundError(f"build_request.json not found in {workdir}")

    with open(request_path) as f:
        request = json.load(f)

    parts = []
    for part in request["parts"]:
        chapters = []
        for ch in part["chapters"]:
            chapters.append({
                "repo": ch["repo"],
                "entry_file": ch["entry_file"],
                "include_path": include_path(ch["repo"], ch["entry_file"]),
            })
        parts.append({"title": part["title"], "chapters": chapters})

    matter_dir = workdir / "matter"
    has_frontmatter = (matter_dir / "Frontmatter.tex").is_file()
    has_postmatter = (matter_dir / "Postmatter.tex").is_file()

    build_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

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

    template = env.get_template("main_book_html.tex.j2")
    rendered = template.render(
        book_title=request["book_title"],
        book_author=book_author,
        parts=parts,
        build_id=build_id,
        build_date=build_date,
        has_frontmatter=has_frontmatter,
        has_postmatter=has_postmatter,
    )

    (workdir / "main.tex").write_text(rendered, encoding="utf-8")
    (workdir / "main_html.tex").write_text(
        "\\PassOptionsToPackage{warpHTML,BaseJobname=main}{lwarp}\n"
        "\\input{main.tex}\n",
        encoding="utf-8",
    )
    print(f"Wrote {workdir / 'main.tex'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render main.tex for book HTML build")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--book-author", default="OpenChapters")
    args = parser.parse_args()

    render(Path(args.workdir), args.build_id, args.book_author)


if __name__ == "__main__":
    main()
