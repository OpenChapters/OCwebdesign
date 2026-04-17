"""
build_chapter_html.py

Renders the main.tex and main_html.tex files for a per-chapter HTML
build using lwarp.

Usage:
    python build_chapter_html.py --workdir /tmp/ochtml-<uuid> \\
        --title "Crystallographic Computations" \\
        --chabbr BASCRY \\
        --authors "Marc De Graef" \\
        --description "An introduction to crystallographic computations." \\
        --include-path "OpenChapters/src/Crystallography/chapter/Crystallography"

It writes:
    <workdir>/main.tex      — lwarp-enabled LaTeX source (arara entry point)
    <workdir>/main_html.tex — lwarp two-pass wrapper
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

import jinja2


def render(
    workdir: Path,
    chapter_title: str,
    chabbr: str,
    authors: str,
    description: str,
    include_path: str,
) -> None:
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

    template = env.get_template("main_chapter_html.tex.j2")
    rendered = template.render(
        chapter_title=chapter_title,
        chabbr=chabbr,
        authors=authors,
        description=description,
        include_path=include_path,
        build_date=build_date,
    )

    main_tex = workdir / "main.tex"
    main_tex.write_text(rendered, encoding="utf-8")
    print(f"Wrote {main_tex}")

    # lwarp two-pass wrapper
    main_html = workdir / "main_html.tex"
    main_html.write_text(
        "\\PassOptionsToPackage{warpHTML,BaseJobname=main}{lwarp}\n"
        "\\input{main.tex}\n",
        encoding="utf-8",
    )
    print(f"Wrote {main_html}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render main.tex + main_html.tex for per-chapter HTML build"
    )
    parser.add_argument("--workdir", required=True, help="Temp build directory path")
    parser.add_argument("--title", required=True, help="Chapter title")
    parser.add_argument("--chabbr", required=True, help="Chapter abbreviation")
    parser.add_argument("--authors", default="", help="Comma-separated author names")
    parser.add_argument("--description", default="", help="Chapter description")
    parser.add_argument("--include-path", required=True, help="LaTeX include path")
    args = parser.parse_args()

    render(
        workdir=Path(args.workdir).resolve(),
        chapter_title=args.title,
        chabbr=args.chabbr,
        authors=args.authors,
        description=args.description,
        include_path=args.include_path,
    )


if __name__ == "__main__":
    main()
