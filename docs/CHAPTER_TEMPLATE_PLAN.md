# OpenChapters Chapter Template Repository — Implementation Plan

## Goal

Create a standalone repository (`OCchaptertemplate`) that authors can clone to write a new chapter for the OpenChapters project. The repository must contain everything needed to typeset a single chapter as a standalone PDF using a standard TeX Live installation — no web platform, Docker, or build server required.

The author works locally with their preferred LaTeX editor on any platform (macOS, Windows, or Linux), compiles and previews their chapter, and submits the result as a pull request or archive to the editors.

---

## Design Principles

1. **Self-contained** — the template includes all `.sty` files, `arara` rules, and support files so `arara main.tex` works out of the box
2. **Minimal** — only the files needed for a single chapter; no multi-chapter infrastructure
3. **Cross-platform** — works on macOS, Windows, and Linux with a standard TeX Live installation
4. **Author-friendly** — clear README with setup instructions, no command-line expertise assumed beyond running `arara` or `pdflatex`
5. **Compatible** — the chapter output integrates seamlessly into the OpenChapters monorepo when accepted

---

## Repository Structure

```
OCchaptertemplate/
├── README.md                   Setup instructions and author guide
├── main.tex                    Standalone wrapper that typesets the chapter
├── chapter/
│   ├── MyChapter.tex           The chapter content (author edits this)
│   ├── chaptercitations.bib    Bibliography for this chapter
│   ├── chapter.json            Metadata (title, authors, toc, etc.)
│   ├── pdf/                    PDF figures (used by pdflatex)
│   │   └── figexample.pdf      Example figure
│   └── eps/                    EPS source figures (optional, for archives)
│       └── figexample.eps      Example figure source
├── style/
│   ├── OpenChapters.sty        OpenChapters style file
│   ├── arara.sty               arara LaTeX package
│   ├── mytodonotes.sty         Custom todo notes
│   ├── preamble.ins            User-defined LaTeX commands
│   └── StyleInd.ist            MakeIndex style
├── matter/
│   ├── Frontmatter.tex         Simplified front matter for standalone build
│   ├── Postmatter.tex          Simplified post matter for standalone build
│   └── pdf/
│       ├── background.pdf      Default cover background
│       └── TOCheader.pdf       Table of contents header image
├── .gitignore
└── LICENSE                     CC BY-NC-SA 4.0
```

---

## Key Files

### `main.tex` — Standalone Chapter Wrapper

A simplified version of the monorepo's `Build/main.tex` that typesets only the author's chapter. Contains:

- arara directives (pdflatex → makeindex → biber → pdflatex × 2 → cleanup)
- `\documentclass[11pt,fleqn,A4paper]{book}`
- `\usepackage{OpenChapters}` (from `style/`)
- `\graphicspath{chapter/pdf/}` pointing to the chapter's figures
- `\addbibresource{chapter/chaptercitations.bib}`
- `\input{matter/Frontmatter}` (simplified)
- `\include{chapter/MyChapter}`
- `\input{matter/Postmatter}` (simplified)

**arara directives** (simplified from the full build):
```
% !TEX TS-program = arara
% arara: clean: {files: ['main-authors.aux'] }
% arara: pdflatex: { shell: yes }
% arara: makeindex: { style: style/StyleInd.ist }
% arara: biber
% arara: pdflatex: { shell: yes }
% arara: pdflatex: { shell: yes }
% arara: clean: { extensions: [aux, bbl, bcf, blg, idx, ilg, ind, log, ptc, toc]}
% arara: clean: { files: ['main.run.xml'] }
```

**Key differences from the full monorepo build:**
- No `copyImageFiles` rule (figures are in a known local directory)
- No `mergemainbibfiles` rule (single bib file)
- No `gitHeadLocal.gin` generation (no gitinfo2 in standalone mode)
- No ImageFolder copy step
- Paths are relative to the template root, not the monorepo Build/ directory

### `chapter/MyChapter.tex` — Chapter Template

Based on `src/ChapterTemplate/OCchapter.tex` with:
- Clear `REPLACE THIS` markers on every field the author must fill in
- Filled-in example content (not just empty sections) so the template compiles out of the box
- Comments explaining each customization point
- Example figure inclusion, table, equation, and citation

### `chapter/chapter.json` — Metadata

Pre-filled with the discipline field and clear placeholder values:
```json
{
  "title": "REPLACE: Your Chapter Title",
  "authors": ["REPLACE: Your Name"],
  "description": "REPLACE: A brief description of this chapter.",
  "toc": [],
  "entry_file": "MyChapter.tex",
  "cover_image": "cover.png",
  "keywords": [],
  "chapter_type": "topical",
  "chabbr": "MYCHAP",
  "depends_on": [],
  "discipline": "mse",
  "published": false
}
```

### `matter/Frontmatter.tex` — Simplified Front Matter

A minimal front matter that produces a simple title page for standalone preview. Does not include the full OpenChapters cover page (which requires `background.pdf` and tikz overlays that may not work standalone). Instead:
- Chapter title and author on a clean title page
- Simplified table of contents
- No copyright page (that's for the full book)

### `matter/Postmatter.tex` — Simplified Post Matter

- Bibliography (printbibliography)
- Index (printindex)
- No appendices or contributor lists

### `README.md` — Author Guide

Sections:
1. **Prerequisites** — TeX Live 2024+, arara, biber, a LaTeX editor
2. **Quick start** — clone, rename, edit, compile
3. **Step-by-step instructions**
   - Rename `chapter/MyChapter.tex` to your chapter name
   - Update `main.tex` to reference the new filename
   - Edit `chapter.json` with your metadata
   - Choose a 6-character `\chabbr` abbreviation
   - Write your content
   - Add figures to `chapter/pdf/`
   - Compile with `arara main.tex` or your editor's build command
4. **Label conventions** — `\chabbr:TYPE:NAME` format explained (TYPE is one of `ch`, `sec`, `ssec`, `eq`, `fig`, `tb`)
5. **Figure conventions** — PDF format, naming, placement
6. **Cross-references** — how to reference other OpenChapters chapters (use `\ref{CHABBR:ch:Name}` for chapter-level refs, `\ref{CHABBR:sec:Name}` for sections, etc.)
7. **Submitting your chapter** — how to package and send to editors
8. **Troubleshooting** — common LaTeX errors and solutions
9. **Style guide** — OpenChapters writing conventions

### `.gitignore`

Excludes LaTeX build artifacts:
```
*.aux *.bbl *.bcf *.blg *.idx *.ilg *.ind *.log *.out
*.ptc *.toc *.run.xml *.synctex.gz *.fdb_latexmk *.fls
main.pdf main-authors.aux
.DS_Store
```

### `LICENSE`

CC BY-NC-SA 4.0 full text.

---

## Implementation Steps

### Step 1: Create the repository structure (~1 hour)

1. Create `../OCchaptertemplate/` directory
2. Copy required style files from `OpenChapters/Build/` into `style/`
3. Copy required matter files (simplified) into `matter/`
4. Copy example figures and bib from `src/ChapterTemplate/`
5. Create `.gitignore` and `LICENSE`

### Step 2: Create `main.tex` wrapper (~30 min)

1. Write a simplified `main.tex` with standalone-friendly arara directives
2. Ensure paths are correct for the template directory layout
3. Remove monorepo-specific features (gitinfo2, ImageFolder, multi-chapter)

### Step 3: Create the chapter template (~30 min)

1. Adapt `OCchapter.tex` into `chapter/MyChapter.tex`
2. Add example content so it compiles out of the box
3. Add clear `REPLACE THIS` markers
4. Create a working `chapter.json` and `chaptercitations.bib`

### Step 4: Create simplified matter files (~30 min)

1. Write `matter/Frontmatter.tex` — simple title page for standalone
2. Write `matter/Postmatter.tex` — bibliography + index only
3. Copy required images (TOCheader.pdf, background.pdf) into `matter/pdf/`

### Step 5: Write README.md (~1 hour)

1. Prerequisites and setup
2. Step-by-step authoring guide
3. Label and figure conventions
4. Submission instructions
5. Troubleshooting

### Step 6: Test compilation (~30 min)

1. Test on macOS with TeX Live + arara
2. Verify the template compiles to a valid PDF
3. Verify that the output chapter can be dropped into the monorepo and compiled as part of a full book

### Step 7: Initialize git repo and push (~15 min)

1. `git init` in `OCchaptertemplate/`
2. Commit all files
3. Create `OpenChapters/OCchaptertemplate` repo on GitHub
4. Push

---

## Compatibility Considerations

### Cross-Platform

- **arara**: included in TeX Live on all platforms; invoked as `arara main.tex`
- **Path separators**: LaTeX uses `/` on all platforms; no Windows `\` issues
- **Encoding**: all files UTF-8
- **Line endings**: `.gitattributes` to normalize (LF in repo, native on checkout)

### Editor Support

The `% !TEX TS-program = arara` directive at the top of `main.tex` tells editors that support it (TeXShop, TeXstudio, VS Code + LaTeX Workshop) to use arara as the build tool. For editors without arara support, the README includes manual compilation commands:

```bash
# If arara is available:
arara -w main.tex

# Manual alternative (all platforms):
pdflatex -shell-escape main
makeindex -s style/StyleInd.ist main
biber main
pdflatex -shell-escape main
pdflatex -shell-escape main
```

### Minimum Requirements

- TeX Live 2024 or later (full installation recommended)
- arara (included in TeX Live)
- biber (included in TeX Live)

---

## Submission Workflow

When an author completes their chapter:

1. Author zips the `chapter/` directory (tex + figures + bib + chapter.json)
2. Sends to editors via email or pull request
3. Editors review the content
4. If accepted, the `chapter/` directory is moved to `src/ChapterName/` in the monorepo
5. `chapter.json` is updated with final metadata
6. Header image is generated
7. Chapter becomes available on the web platform after the next sync

---

## Future Enhancement

A GitHub Actions workflow could be added to the template repo that:
1. Compiles the chapter on push (CI validation)
2. Uploads the PDF as a build artifact
3. Runs a basic lint (check for required labels, chabbr format, etc.)

This is optional and can be added after the initial release.
