# HTML Output Integration Plan

This document describes how the existing lwarp-based HTML build (in the `OpenChapters/HTMLBuild` folder) could be integrated with the OpenChapters web platform.

## Background

The `HTMLBuild` folder contains a working lwarp setup that converts LaTeX chapter source into HTML5 pages with MathJax-rendered equations, SVG figures, responsive CSS, and side-panel table of contents. The build is orchestrated by arara and uses `main_html.tex` as the lwarp entry point. Output is a set of static HTML files (`index.html`, `node-1.html`, etc.) plus an `ImageFolder/` of SVG assets.

The current web platform only produces PDF output via the `build_book` Celery task. Adding an HTML reading option would let users read chapters directly in the browser without waiting for a PDF build.

---

## Integration Approaches

### Approach 1: Per-Chapter HTML (Recommended Starting Point)

Generate HTML for each chapter individually and serve it inline on the chapter detail page.

**Workflow:**

1. A new Celery task (`build_chapter_html`) runs lwarp on a single chapter
2. Output is stored under `/app/media/html/<chabbr>/` (index.html, node-\*.html, images/)
3. The chapter detail page gains a **"Read Online"** tab or button, rendering the lwarp HTML in an iframe or a dedicated `/chapters/:id/read` route
4. The existing cover image, TOC preview, and metadata remain; the HTML version adds full-content reading

**Pros:**
- Each chapter is independently viewable without building a whole book
- Fits the browse-then-read workflow
- Can be cached and served as static files
- Small storage footprint (100-500 KB per chapter)

**Cons:**
- Cross-chapter references (`\ref`, `\cite`) won't resolve across chapters
- Each chapter build needs a wrapper `main.tex` that loads the full preamble

### Approach 2: Per-Book HTML (Parallels the PDF Pipeline)

When a user builds a book, offer "Build as HTML" alongside or instead of "Build as PDF."

**Workflow:**

1. The existing `build_book` task already assembles `main.tex` from selected chapters; a variant uses the `main_html.tex` + lwarp path
2. Output is a set of HTML files stored alongside the PDF in build artifacts
3. The Library page shows both "Download PDF" and "View Online" buttons
4. The HTML version is a multi-page site with lwarp's built-in navigation (side TOC, prev/next links)

**Pros:**
- Cross-references and bibliography work correctly across all selected chapters
- The user gets exactly their custom book in HTML form
- Closest to what HTMLBuild already does

**Cons:**
- Requires a full LaTeX build (2-3 minutes), same as PDF
- Cannot preview individual chapters before building
- More storage per build

### Approach 3: Hybrid (Best of Both)

- **Per-chapter HTML** for the public chapter browser (read individual chapters online)
- **Per-book HTML** as an optional build output (full custom assembly as a navigable website)

This gives immediate value through individual chapter reading, with the per-book option added later.

---

## Technical Considerations

### 1. Build Environment

The worker Docker image already has TeX Live, arara, and the full LaTeX toolchain. Adding lwarp support requires:

- The `lwarp` LaTeX package (likely already included in TeX Live)
- `OpenChaptersHTML.sty` and `preambleHTML.ins` added to the Build/template files
- `pdf2svg` or equivalent for figure conversion (PDF to SVG)
- Sufficient `/tmp` space for intermediate build artifacts

### 2. Per-Chapter Wrapper

lwarp needs a `main.tex` with the full preamble. For per-chapter builds, a minimal wrapper would be generated (analogous to what `build_main_tex.py` already does for PDF):

```latex
\documentclass[11pt,fleqn,a4paper]{book}
\usepackage[
    makeindex,
    ImagesDirectory=ImageFolder,
    HomeHTMLFilename=index,
    HTMLFilename={node-},
    latexmk,
    mathjax,
]{lwarp}
\usepackage{OpenChaptersHTML}
\input{preambleHTML.ins}
\begin{document}
\include{src/<chapter_subdir>/chapter/<entry_file>}
\end{document}
```

The existing Jinja2 template system in `build_main_tex.py` could be extended with an HTML variant template.

### 3. MathJax

lwarp output uses MathJax 3 (loaded from `cdn.jsdelivr.net`) for equation rendering. This means:

- HTML pages need internet access to render math (or MathJax must be bundled locally)
- The nginx Content-Security-Policy header needs `script-src` and `font-src` additions for the MathJax CDN
- The existing `lwarp_mathjax.txt` configuration handles equation numbering, subequations, and custom LaTeX macros

### 4. CSS Theming

lwarp generates HTML with its own CSS classes. Two approaches to visual integration:

- **Iframe isolation:** Serve lwarp HTML in an iframe within the React app. Styles don't conflict; lwarp's own CSS (e.g., `lwarp_sagebrush.css`) applies cleanly. The iframe approach is simpler but limits interaction between the React shell and the chapter content.
- **Embedded with adapted CSS:** Inject lwarp HTML directly into a React component and adapt `lwarp_sagebrush.css` to match the OpenChapters site design. More integrated but requires careful CSS scoping to prevent conflicts.

### 5. SVG Images

lwarp converts PDF figures to SVG for web display. Each chapter build needs its own image directory to avoid filename collisions. The existing `\graphicspath` mechanism and the lwarp `ImagesDirectory` option handle this naturally.

### 6. Navigation

lwarp generates its own prev/next navigation bars and a side table of contents. For per-chapter viewing embedded in the React app:

- Strip lwarp's navigation chrome (header/footer nav bars)
- Use the site's own UI for chapter-level navigation
- Keep lwarp's intra-chapter section links (they work within the generated HTML)

For per-book HTML builds, lwarp's navigation can be kept as-is since the user is viewing a standalone multi-chapter document.

### 7. Storage and Caching

- Per-chapter HTML + SVG: typically 100-500 KB per chapter (negligible)
- Per-book HTML builds: comparable to PDF size, stored alongside PDFs in the media volume
- HTML can be regenerated on each nightly sync or on-demand from the admin panel
- Cache-busting via the existing `cached_at` timestamp mechanism

---

## Recommended Implementation Order

**Phase 1 — Per-chapter HTML reading (Approach 1):**

1. Add `pdf2svg` to the worker Docker image
2. Create a `build_chapter_html.py` management command that builds one chapter's HTML using a Jinja2 wrapper template
3. Add an admin action "Build HTML" (similar to "Update Thumbnails") that triggers HTML generation for all published chapters
4. Store output in `media/html/<chabbr>/`
5. Add a "Read Online" button on the chapter detail page
6. Serve via a new route `/chapters/:id/read` that loads the HTML in an iframe or embedded view
7. Update the nginx CSP header to allow MathJax CDN resources

**Phase 2 — Nightly automation:**

8. Integrate HTML builds into the `sync_chapters` nightly task (rebuild HTML when source changes)
9. Add cache invalidation so updated chapters get fresh HTML

**Phase 3 — Per-book HTML (Approach 2, optional):**

10. Extend `build_book` to accept an output format parameter (`pdf`, `html`, or `both`)
11. Create an HTML variant of the `main.tex` Jinja2 template
12. Add "View Online" to the Library page alongside "Download PDF"

---

## Open Questions

- **Bibliography:** Per-chapter builds won't have a merged bibliography. Should each chapter include its own `.bib` file, or should citations be rendered as inline text without hyperlinked references?
- **Cross-references:** Chapters that depend on other chapters (via `depends_on`) may have broken `\ref` links in per-chapter HTML. Should these be removed, converted to text, or linked to the other chapter's HTML?
- **Mobile support:** lwarp's default CSS is responsive but not mobile-optimized. Should a custom mobile CSS be developed?
- **Offline reading:** Should the HTML output be downloadable as a zip for offline use?
- **Search:** With chapter content available as HTML, full-text search across all chapters becomes feasible. Is this a desired feature?
