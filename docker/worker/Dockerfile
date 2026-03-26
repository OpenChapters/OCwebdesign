# ─────────────────────────────────────────────────────────────────────────────
# OpenChapters — LaTeX worker image
#
# Builds the container that runs the Celery build_book task.  It is responsible
# for cloning chapter repos, running the Python pipeline scripts, and invoking
# arara to typeset the PDF.
#
# Build context: repo root (OCwebdesign/)
#   docker build -f docker/worker/Dockerfile -t ocbuild-worker .
#
# Key paths inside the image:
#   /opt/ocbuild/Build/scripts/   Python pipeline scripts
#   /opt/ocbuild/Build/template/  LaTeX template files (.sty, .ins, .ist)
#                                 copied into every temp workspace at build time
#   /opt/ocbuild/arara-rules/     Custom arara rule definitions
#   /usr/local/bin/copyImageFiles      wrapper → collect_images.py
#   /usr/local/bin/mergemainbibfiles   wrapper → concat_bibs.py
#   /root/.araraconfig.yaml        global arara config (rule search path)
# ─────────────────────────────────────────────────────────────────────────────

FROM texlive/texlive:latest

# ── System packages ───────────────────────────────────────────────────────────
# arara, biber, and the full TeX Live package set are already included in the
# base image (~5 GB).  We add only what the base lacks.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 \
      python3-pip \
      git \
 && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────────────
# jinja2  — used by build_main_tex.py to render main.tex from the template
# httpx   — used by the GitHub client for chapter catalog sync
RUN pip3 install --no-cache-dir --break-system-packages \
      jinja2 \
      httpx

# ── Python project dependencies ───────────────────────────────────────────────
# The Celery worker imports Django models and tasks, so the full project
# requirements must be installed here too.
COPY requirements/ /tmp/requirements/
RUN pip3 install --no-cache-dir --break-system-packages \
      -r /tmp/requirements/base.txt

# ── Project files ─────────────────────────────────────────────────────────────
WORKDIR /opt/ocbuild

# Pipeline Python scripts and shell wrappers
COPY Build/scripts/ Build/scripts/

# Custom arara rule definitions (copyImageFiles, mergemainbibfiles)
COPY arara-rules/ arara-rules/

# LaTeX template files copied into every temp build workspace.
# These are NOT in this repo — they live in the OpenChapters repo.
# Before building this image, copy the following files from
# OpenChapters/Build/ into Build/template/ alongside this repo:
#
#   OpenChapters.sty    main style file
#   mytodonotes.sty     custom local .sty (not on CTAN)
#   arara.sty           custom local .sty (not on CTAN)
#   preamble.ins        user-defined LaTeX commands
#   StyleInd.ist        makeindex style file
#
COPY Build/template/ Build/template/

# ── Wrapper shell scripts ─────────────────────────────────────────────────────
# The arara rules invoke these by name via: bash -i -c 'copyImageFiles'
# They must be on PATH so bash can find them without sourcing a .bashrc.
RUN install -m 0755 Build/scripts/copyImageFiles  /usr/local/bin/copyImageFiles \
 && install -m 0755 Build/scripts/mergemainbibfiles /usr/local/bin/mergemainbibfiles

# ── arara global configuration ────────────────────────────────────────────────
# Tells arara to search /opt/ocbuild/arara-rules/ for rule files regardless of
# the CWD (which is the per-request temp workspace, not this directory).
# arara 6+ config format; tested against TeX Live 2024 (arara 7.x).
RUN printf '!config\npaths:\n  - /opt/ocbuild/arara-rules\n' \
      > /root/.araraconfig.yaml

# ── Environment ───────────────────────────────────────────────────────────────
# OCBUILD_SCRIPTS_DIR is read by the wrapper shell scripts installed above.
ENV OCBUILD_SCRIPTS_DIR=/opt/ocbuild/Build/scripts

# The Django/Celery process runs from /app (mounted as a volume in dev).
# Temp build workspaces are created under /tmp by the build_book task;
# arara is invoked via subprocess with an explicit path to main.tex.
ENV DJANGO_SETTINGS_MODULE=ocweb.settings.dev

# texlive user (UID 1000) already exists in the base image
USER texlive
WORKDIR /app
