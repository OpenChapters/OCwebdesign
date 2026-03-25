"""
collect_images.py

Collects figure files from chapter directories into ImageFolder/ in the
build workspace.

Replaces the copyImageFiles bash function previously defined in ~/.bashrc.

For monorepo builds, chapters live under a subdirectory of the cloned repo
(e.g. OpenChapters/src/LinearAlgebra/).  Each chapter entry in
build_request.json may include a "chapter_subdir" field (e.g.
"src/LinearAlgebra") that is appended to the cloned repo directory to locate
the chapter's figures.  If "chapter_subdir" is absent, the repo root is used
(backward-compatible with per-chapter repo builds).

Figure directories searched (in order of preference):
  <content_dir>/pdf/   — PDF figures (preferred; produced by figure migration)
  <content_dir>/eps/   — EPS + PDF figures (legacy per-chapter repo layout)

Usage:
    python collect_images.py --workdir /tmp/ocbuild-<uuid>

The script expects:
    <workdir>/build_request.json       — book assembly spec
    <workdir>/<repo-dir>/<chapter_subdir>/pdf/  — PDF figures (monorepo)
    <workdir>/<repo-dir>/<chapter_subdir>/eps/  — EPS figures (legacy)
    <workdir>/matter/eps/              — matter figure directory (optional)

It writes:
    <workdir>/ImageFolder/<filename>   — all collected figure files
"""

import argparse
import json
import shutil
from pathlib import Path


def repo_dirname(repo: str) -> str:
    """Return the local directory name for a cloned repo.

    "OpenChapters/OpenChapters" -> "OpenChapters"
    """
    return repo.split("/")[-1]


def collect(workdir: Path) -> None:
    request_path = workdir / "build_request.json"
    if not request_path.exists():
        raise FileNotFoundError(f"build_request.json not found in {workdir}")

    with open(request_path) as f:
        request = json.load(f)

    image_dir = workdir / "ImageFolder"
    image_dir.mkdir(exist_ok=True)

    total = 0
    seen_repos: set[str] = set()

    for part in request["parts"]:
        for ch in part["chapters"]:
            repo = ch["repo"]
            chapter_subdir = ch.get("chapter_subdir", "")

            repo_dir = workdir / repo_dirname(repo)
            content_dir = repo_dir / chapter_subdir if chapter_subdir else repo_dir

            # Prefer pdf/ (figure-migration output); fall back to eps/ (legacy)
            pdf_dir = content_dir / "pdf"
            eps_dir = content_dir / "eps"

            if pdf_dir.is_dir():
                for src in sorted(pdf_dir.glob("*.pdf")):
                    shutil.copy2(src, image_dir / src.name)
                    total += 1
            elif eps_dir.is_dir():
                for pattern in ("*.eps", "*.pdf"):
                    for src in sorted(eps_dir.glob(pattern)):
                        shutil.copy2(src, image_dir / src.name)
                        total += 1
            else:
                print(
                    f"  WARNING: no pdf/ or eps/ directory in {content_dir.relative_to(workdir)}, skipping"
                )

    # Collect matter figures: .pdf only
    matter_eps = workdir / "matter" / "eps"
    if matter_eps.is_dir():
        for src in sorted(matter_eps.glob("*.pdf")):
            shutil.copy2(src, image_dir / src.name)
            total += 1
    else:
        print(f"  WARNING: matter/eps/ not found in {workdir}, skipping")

    print(f"collect_images: copied {total} file(s) to {image_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect chapter and matter figures into ImageFolder/"
    )
    parser.add_argument(
        "--workdir",
        default=".",
        help="Temp build directory path (default: current directory)",
    )
    args = parser.parse_args()

    collect(Path(args.workdir).resolve())


if __name__ == "__main__":
    main()
