"""
concat_bibs.py

Concatenates per-chapter bibliography files into a single OpenChapters.bib
in the build workspace.

Replaces the mergemainbibfiles bash function previously defined in ~/.bashrc.

For monorepo builds, chapters live under a subdirectory of the cloned repo
(e.g. OpenChapters/src/LinearAlgebra/).  Each chapter entry in
build_request.json may include a "chapter_subdir" field (e.g.
"src/LinearAlgebra") that is appended to the cloned repo directory to locate
the chapter's bib file.  If "chapter_subdir" is absent, the repo root is used
(backward-compatible with per-chapter repo builds).

Usage:
    python concat_bibs.py --workdir /tmp/ocbuild-<uuid>

The script expects:
    <workdir>/build_request.json                              — book assembly spec
    <workdir>/<repo-dir>/<chapter_subdir>/chaptercitations.bib

It writes:
    <workdir>/OpenChapters.bib   — merged bibliography ready for biber
"""

import argparse
import json
from pathlib import Path


def repo_dirname(repo: str) -> str:
    """Return the local directory name for a cloned repo.

    "OpenChapters/OpenChapters" -> "OpenChapters"
    """
    return repo.split("/")[-1]


def concat(workdir: Path) -> None:
    request_path = workdir / "build_request.json"
    if not request_path.exists():
        raise FileNotFoundError(f"build_request.json not found in {workdir}")

    with open(request_path) as f:
        request = json.load(f)

    bib_out = workdir / "OpenChapters.bib"
    found = 0
    missing = []

    with open(bib_out, "w", encoding="utf-8") as out:
        for part in request["parts"]:
            for ch in part["chapters"]:
                repo = ch["repo"]
                chapter_subdir = ch.get("chapter_subdir", "")

                repo_dir = workdir / repo_dirname(repo)
                content_dir = repo_dir / chapter_subdir if chapter_subdir else repo_dir
                bib_src = content_dir / "chaptercitations.bib"

                if not bib_src.exists():
                    missing.append(str(bib_src.relative_to(workdir)))
                    continue
                out.write(bib_src.read_text(encoding="utf-8"))
                # Ensure a blank line between concatenated files
                out.write("\n")
                found += 1

    if missing:
        print(f"  WARNING: missing bib file(s): {', '.join(missing)}")
    if found == 0:
        raise RuntimeError(
            "concat_bibs: no chaptercitations.bib files found — "
            "OpenChapters.bib would be empty; aborting"
        )

    print(f"concat_bibs: merged {found} bib file(s) into {bib_out}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge per-chapter bib files into OpenChapters.bib"
    )
    parser.add_argument(
        "--workdir",
        default=".",
        help="Temp build directory path (default: current directory)",
    )
    args = parser.parse_args()

    concat(Path(args.workdir).resolve())


if __name__ == "__main__":
    main()
