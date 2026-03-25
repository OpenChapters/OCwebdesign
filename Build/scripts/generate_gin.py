"""
generate_gin.py

Writes a synthetic gitHeadLocal.gin into the temp build directory so
that the gitinfo2 LaTeX package works without a real .git/ directory.

Must be run BEFORE arara. The generated main.tex omits the arara
'copy' directive that would normally copy ../.git/gitHeadInfo.gin.

gitinfo2 is loaded in OpenChapters.sty with the [local,mark] options:
    \\usepackage[local,mark]{gitinfo2}

The [local] option tells gitinfo2 to read gitHeadLocal.gin from the
current directory rather than searching up the directory tree. This
script satisfies that requirement with web-build metadata.

The resulting page footer (via \\gitMark in OpenChapters.sty) reads:
    [OpenChapters Web Build] Branch: web-build @ <short-id>
    • Release: web-<YYYY-MM-DD> (<YYYY-MM-DD>)

Usage:
    python generate_gin.py --workdir /tmp/ocbuild-<uuid> --build-id <uuid>
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

GIN_TEMPLATE = """\
\\usepackage[%
        shash={{{short_id}}},
        lhash={{{build_id}}},
        authname={{OpenChapters Web}},
        authemail={{}},
        authsdate={{{sdate}}},
        authidate={{{idate}}},
        authudate={{{udate}}},
        commname={{OpenChapters Web}},
        commemail={{}},
        commsdate={{{sdate}}},
        commidate={{{idate}}},
        commudate={{{udate}}},
        refnames={{ (HEAD -> web-build)}},
        firsttagdescribe={{{reltag}}},
        reltag={{{reltag}}}
    ]{{gitexinfo}}
"""


def generate(workdir: Path, build_id: str) -> None:
    now = datetime.now(timezone.utc)
    sdate = now.strftime("%Y-%m-%d")
    idate = now.strftime("%Y-%m-%d %H:%M:%S +0000")
    udate = str(int(now.timestamp()))
    short_id = build_id[:7]
    reltag = f"web-{sdate}"

    content = GIN_TEMPLATE.format(
        short_id=short_id,
        build_id=build_id,
        sdate=sdate,
        idate=idate,
        udate=udate,
        reltag=reltag,
    )

    output_path = workdir / "gitHeadLocal.gin"
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic gitHeadLocal.gin for a web build"
    )
    parser.add_argument("--workdir", required=True, help="Temp build directory path")
    parser.add_argument("--build-id", required=True, help="Build UUID")
    args = parser.parse_args()

    generate(Path(args.workdir), args.build_id)


if __name__ == "__main__":
    main()
