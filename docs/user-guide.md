# OpenChapters User Guide

OpenChapters is a free, open-source platform for building custom PDF textbooks from a library of LaTeX-typeset chapters. This guide walks you through every step, from creating an account to downloading your finished book.

---

## Table of Contents

1. [Creating an Account](#creating-an-account)
2. [Signing In](#signing-in)
3. [Browsing Chapters](#browsing-chapters)
4. [Chapter Catalog](#chapter-catalog)
5. [Searching Chapter Content](#searching-chapter-content)
6. [Reading a Chapter Online](#reading-a-chapter-online)
7. [Chapter Details](#chapter-details)
8. [Creating a Book](#creating-a-book)
9. [The Book Editor](#the-book-editor)
   - [Adding Parts](#adding-parts)
   - [Adding Chapters](#adding-chapters)
   - [Reordering Chapters](#reordering-chapters)
   - [Reordering Parts](#reordering-parts)
   - [Moving Chapters Between Parts](#moving-chapters-between-parts)
   - [Removing Chapters and Parts](#removing-chapters-and-parts)
   - [Auto-Include Foundational Chapters](#auto-include-foundational-chapters)
10. [Building Your Book](#building-your-book)
11. [Build Status](#build-status)
12. [Your Library](#your-library)
13. [Community Library](#community-library)
14. [Worked Examples](#worked-examples)
    - [Browsing](#browsing)
    - [Reading an Example](#reading-an-example)
    - [Submitting an Example](#submitting-an-example)
    - [Lifecycle](#lifecycle)
    - [Batch Import](#batch-import)
    - [Where Examples Appear](#where-examples-appear)
15. [Managing Your Books](#managing-your-books)
16. [Your Profile](#your-profile)
17. [Resetting Your Password](#resetting-your-password)
18. [Feature Requests and Bug Reports](#feature-requests-and-bug-reports)

---

## Creating an Account

1. Click **Register** in the top-right corner of the navigation bar.
2. Enter your **full name** (used on book cover pages).
3. Enter your **email address** and choose a **password** (minimum 8 characters).
4. Complete the CAPTCHA verification (Cloudflare Turnstile).
5. Click **Create account**.
6. You will be redirected to the sign-in page. Enter your credentials to log in.

Your email address is your login identifier and will be used for PDF delivery notifications. Your full name appears on the cover page of books you build.

## Signing In

1. Click **Sign in** in the navigation bar.
2. Enter your email and password.
3. Click **Sign in**.

If you forget your password, click **Forgot password?** on the sign-in page. See [Resetting Your Password](#resetting-your-password) for details.

Your session stays active for up to 7 days. The access token refreshes automatically in the background — you don't need to sign in again unless you've been inactive for a full week.

## Browsing Chapters

The **Chapter Browser** is the main page of the site, accessible by clicking **Browse** in the navigation bar or visiting the home page.

### Discipline Filter

When multiple disciplines are available, a row of selector buttons appears at the top of the page:

- **All Disciplines** — shows chapters from all disciplines (default)
- **Per-discipline buttons** — click to filter to a single discipline (e.g., "Materials Science and Engineering")

Your selected discipline is remembered across page visits. When "All Disciplines" is selected, each chapter card shows a colored badge indicating its discipline.

### Chapter Organization

Within each discipline (or across all), chapters are organized into two sections:

- **Topical Chapters** — specialized topics (displayed first)
- **Foundational Chapters** — core mathematical and scientific background

Each chapter is displayed as a card showing:
- Chapter title
- Author(s)
- Keywords (if available)
- A cover image or placeholder icon

### Quick Filter

Use the search box in the top-right of the Browse page to filter chapter cards by title, author, or keyword. This is a fast metadata filter — it does not search inside the chapter text. For content-level search across all chapters, see [Searching Chapter Content](#searching-chapter-content).

### Hover Preview

Hover your mouse over any chapter card to see a **table of contents** popover listing the sections within that chapter. This lets you quickly assess whether a chapter covers the topics you need.

## Chapter Catalog

Click **Catalog** in the top navigation bar to open a flat, read-only inventory of every published chapter. The catalog page is public — no account is required — and is intended as a quick reference for prospective authors who want to see what is already in the collection before contributing.

Each row shows the chapter title, abbreviation (`chabbr`), discipline, type (foundational or topical), authors, the date of the most recent commit touching the chapter's source, and the number of published [worked examples](#worked-examples) tagged to the chapter (click the count to jump to those examples). A **discipline** filter at the top lets you narrow the view.

Click **Download CSV** to download the same data as a spreadsheet (`openchapters-catalog.csv`). The file is UTF-8 encoded with a byte-order mark, so accented characters open correctly in Excel and Numbers, and includes both an `examples` column with the count and a `url` column that links each row to its public chapter detail page.

## Searching Chapter Content

Click **Search** in the top navigation bar to open the full-text search page. Type a query and results appear as you type:

- Each result shows the chapter, the section heading that contains the match, and a short snippet with the matching term(s) highlighted in yellow.
- Each whitespace-separated word is matched as a **prefix** by default, so typing `sym` finds `symbol`, `symmetry`, `symmetric`, etc.
- Supports phrases in quotes (`"rotation matrix"`), required terms (`+quaternion euler`), and boolean OR. When a quoted phrase, an `OR`, or a `-` exclusion appears in the query, prefix expansion is turned off and the query is parsed as a strict PostgreSQL `websearch` expression.
- Clicking a result opens that chapter's HTML reader and jumps directly to the matching section.

The search index covers every published chapter that has an HTML version available. Chapters without an HTML build are excluded from search results.

## Reading a Chapter Online

Chapters with an HTML version available have a **Read Online** button on their detail page. This opens an in-browser reader with:

- The full chapter content, rendered with MathJax equations and SVG figures.
- A side table of contents on the left, listing all sections within the chapter.
- A small chapter thumbnail at the top of the side TOC.

Not every chapter has an HTML version. When it is not available, only the **+ Add to Book** button appears on the chapter detail page — you can still include the chapter in a custom PDF build.

**About cross-references.** Per-chapter HTML is built from that chapter's source only. Any cross-reference that points to a label in a different chapter will render as the label name in italics (e.g., *NUMSYS:sec:quaternions*) rather than a live link. Cross-chapter hyperlinks will become possible in per-book HTML builds (planned feature).

## Chapter Details

Each chapter card has two buttons:

- **Chapter Info** — opens the full chapter detail page showing:
  - Complete table of contents
  - Author(s) and description
  - Keywords
  - Chapter type (foundational or topical)
  - Dependencies on other foundational chapters
  - A **Read Online** button (if the chapter has an HTML version)
  - A **Download PDF (with labels)** button — appears only on **foundational** chapters that have a labels-PDF artifact built. The PDF is the chapter typeset with `\showkeys`, so every section, equation, figure, and table label is printed next to its anchor. Useful when writing a new chapter that needs to cross-reference foundational material — you can copy the exact label key from the PDF.
  - An **+ Add to Book** button

- **+ Add to Book** — opens the chapter detail page with the book picker already visible. You can:
  - Select an existing draft book to add the chapter to
  - Click **+ Create new book** to start a new book with this chapter

When you add a chapter from the detail page, it is placed in the first part of the chosen book. You can rearrange it later in the Book Editor.

## Creating a Book

There are two ways to create a new book:

### From the Chapter Browser
Click **+ Add to Book** on any chapter card, then choose **+ Create new book**. You will be prompted to enter a book title, then the book is created with the selected chapter already added.

### From My Books
1. Click **My Books** in the navigation bar.
2. Click the **+ New Book** button.
3. Enter a title for your book.
4. Click **Create**. You will be taken to the Book Editor.

## The Book Editor

The Book Editor is a split-panel interface for assembling your book:

- **Left panel** — Chapter Catalog: browse and search all available chapters
- **Right panel** — Book Structure: your book's parts and chapters

### Editing the Book Title

Click the book title at the top of the page (next to the pencil icon) to edit it. Press Enter or click **Save** to confirm.

### Cover Page Image

Below the "Book Structure" header, you'll find the **Cover Page Image** section:

- By default, a standard OpenChapters cover design is used.
- Click **Upload PDF** to upload a custom cover page image (PDF format, max 50MB).
- The PDF should be A4-size with two color images (298 points / ~105mm tall each) spanning the full page width, separated by a white background.
- Click **Replace** to change the uploaded image, or **Remove** to revert to the default.
- Uploaded cover images are archived with your account and persist across book rebuilds.

### DOI

An optional **DOI** field is available below the cover image section. Type a DOI identifier (e.g., `10.1234/openchapters.2026`) and click away to save. Leave blank if not applicable.

### TOC Preview

Click **Preview TOC** in the header bar to see a compact preview of your book's structure:
- Shows the book title, each part with its number, and the chapters within each part.
- Useful for verifying the structure before building.
- Click **Hide Preview** to close.

### Build Status Indicator

After triggering a build, a **status badge** appears in the header bar:
- **Yellow (Queued)** — waiting to start
- **Blue (Building)** — typesetting in progress
- **Green (PDF Ready — View)** — click to go to the download page
- **Red (Build Failed — View)** — click to see the error

The editor stays open during the build, and you receive a toast notification when it completes or fails.

### Adding Parts

Books are organized into **parts** (corresponding to LaTeX `\part{}` commands). Each part has a title and contains an ordered list of chapters.

1. Scroll to the bottom of the Book Structure panel.
2. Type a part title in the "New part title…" field.
3. Click **Add Part**.

To rename a part, click the pencil icon (✎) on its header.

### Adding Chapters

1. Click a part header in the right panel to make it the **active part** (indicated by a blue border and "(active)" label).
2. In the left panel, find the chapter you want to add.
3. Click the **+ Add** button on the chapter card.

The chapter appears in the active part. Chapters that are already in your book show "✓ Added" instead of a button.

The "Adding to: **Part Name**" indicator below the search box confirms which part will receive new chapters.

### Reordering Chapters

Drag and drop chapters within a part to change their order:

1. Grab the drag handle (⠿) on the left side of a chapter.
2. Drag it up or down within the same part.
3. Release to drop it in the new position.

The new order is saved automatically.

### Reordering Parts

To change the order of parts in your book:

1. Click the **▲** (up) or **▼** (down) arrow on the part header.
2. The part swaps position with its neighbor.

The first part disables the up arrow and the last part disables the down arrow.

### Moving Chapters Between Parts

You can drag a chapter from one part to another:

1. Grab the drag handle (⠿) on a chapter.
2. Drag it over a different part.
3. Drop it — the chapter is removed from the original part and added to the destination part.

The destination part highlights with a blue background when you hover over it.

### Removing Chapters and Parts

- To **remove a chapter** from a part, click the **×** button on the right side of the chapter row.
- To **delete a part** (and all its chapters), click the trash icon (🗑) on the part header. You will be asked to confirm.

### Auto-Include Foundational Chapters

When you add a topical chapter, the system checks whether it references any foundational chapters that are not yet in your book. If dependencies are detected, an amber banner appears:

> **Required foundational chapters**
> The topical chapters you selected reference these foundational chapters.

You can:
- Click **+ Add** next to individual chapters to include them
- Click **Add all** to include all suggested chapters at once
- Click **Dismiss** to hide the banner

Even if you dismiss the banner, the build system will **automatically include** any foundational chapters required by your selected topical chapters. This ensures that all cross-chapter references resolve correctly in the final PDF. Auto-included chapters appear in a **Foundations** part at the beginning of the book.

If you add the foundational chapters yourself, you can place them in any part and in any order you prefer.

## Building Your Book

Once your book has at least one chapter:

1. Choose a **build format** from the drop-down next to the Build button:
   - **PDF** — a professionally typeset PDF (default)
   - **HTML** — an interactive, browser-based version with side-panel table of contents, MathJax-rendered equations, and SVG figures
   - **PDF + HTML** — run both builds one after the other in a single request
2. *(Optional, when at least one [worked example](#worked-examples) is tagged to a chapter in your book)* Toggle the example checkboxes:
   - **Include N examples** — appends a "Worked examples" section to each chapter that has tagged examples. On by default. The number reflects distinct published examples that will appear; cross-chapter examples render once, under whichever tagged chapter appears earliest in the book.
   - **with solutions** — when off, statements appear without solutions, producing a problem-only handout from the same corpus. Greyed out when "Include N examples" is off.
3. Click the **Build** button in the top-right corner of the Book Editor.
4. Confirm the build in the dialog.

The build process typically takes 1–3 minutes per format depending on the number of chapters and figures. During a build, the server:

- Clones the chapter source files from GitHub
- Merges bibliographies and collects figures
- Typesets the book using LaTeX (pdflatex + biber + makeindex for PDF, plus lwarp + MathJax for HTML)
- Produces the PDF and/or a complete HTML bundle ready for offline reading

## Build Status

The Build Status page shows the current state of your build:

| Status | Meaning |
|---|---|
| **Queued** | Build is waiting to start |
| **Building** | LaTeX typesetting is in progress |
| **Complete** | PDF is ready |
| **Failed** | An error occurred during typesetting |

The page polls automatically every 3 seconds while the build is in progress.

The page also shows the **book title** so you know which build you're monitoring.

If the build **succeeds**, a **Download PDF** button appears (and, for an HTML build, a **View Online** link). If email delivery is configured on the server, you will also receive an email with download links that remain valid for 7 days. If the build **fails**, the error message from the LaTeX log is shown to help diagnose the issue.

## Your Library

Click **Library** in the navigation bar to see all your completed books. Each entry shows:

- Book title
- Completion date
- A **Build info** link to view the build status
- A **Download PDF** button (when a PDF build is available)
- A **View Online** link and **Download HTML** button (when an HTML build is available)

The **View Online** link opens the full book in the browser with clickable table of contents, search-friendly text, and MathJax-rendered equations. **Download HTML** gives you a zip archive of the complete site (HTML pages, CSS, SVG figures, MathJax configuration) that you can open locally with any web browser — no server required.

## Community Library

Click **Community** in the top navigation bar to see books that other contributors have chosen to share. The page is public — anyone can view it.

Each entry shows:

- The book title and the author's display name (full name, or "Anonymous" if not set). Email addresses are never shown.
- The build date.
- The full part-and-chapter structure of the book, with each chapter title linking to its detail page so you can read or borrow individual chapters.

Sharing is **listing-only**: PDFs and HTML readers are not exposed publicly. Instead, every entry has a **Clone to my books** button (when you are signed in). Clicking it:

1. Copies the book's parts and chapters into a new draft owned by you, titled `Copy of <original>`.
2. Drops you into the Book Editor for the new draft.
3. Leaves the original alone — the cover image, DOI, and build artifacts of the source are not copied.

You can then edit the title, set your own cover, add or remove chapters, and build it under your own identity (your name appears on the cover, your gitinfo footer, your library). To see a build you cloned, look in **My Books**.

If you are not signed in, the Clone button is replaced with a **Sign in to clone** link.

To make your own completed books visible on this page, enable the **Visibility** option on your [profile](#your-profile).

## Worked Examples

The **worked examples library** is a community-contributed corpus of LaTeX problems with full solutions, each tagged to one or more chapters. Click **Examples** in the navigation bar to browse them, or look for an "Examples" section on any chapter detail page that has tagged entries.

### Browsing

The `/examples` page lists every published example as a single column of cards. Each card shows the difficulty (introductory / standard / advanced), the chapter abbreviations the example is tagged to, the contributor's display name, and a short preview of the statement. Filters at the top of the page narrow the list:

- **Chapter** — restrict to examples tagged to a specific chapter (by chabbr).
- **Difficulty** — introductory, standard, or advanced.
- **Search** — case-insensitive substring match against the statement and solution text.

Click any card to open the detail page.

### Reading an Example

The detail page renders both the statement and the solution. Inline math (`$..$`, `\(..\)`) and display math (`$$..$$`, `\[..\]`) is rendered in-browser via KaTeX; everything else is shown verbatim. KaTeX is best-effort — custom OpenChapters macros and complex environments will not render but will not crash the page either; in those cases the source falls through highlighted in amber.

For full-fidelity rendering (the same LaTeX pipeline used to build chapters), click **Open preview PDF** to fetch the typeset version.

A **Show / Hide** toggle on the solution lets you read the statement first and try the problem yourself before revealing the solution.

### Submitting an Example

Anyone with an account can submit an example.

1. Click **Submit an example** on the `/examples` page (or **+ New example** from your [profile](#your-profile)).
2. Pick the **chapters** the example applies to. At least one is required; you may tag several.
3. Choose a **primary chapter** from the chapters you tagged. The primary chapter determines which preamble is used to compile the snippet preview, and (in book builds) which chapter the example renders under when more than one of its tags ends up in the same book.
4. Pick a **difficulty**.
5. Paste the LaTeX source for the **statement** and **solution** into the two textareas. The form does not constrain the LaTeX — anything that compiles in a standard OpenChapters preamble will work.
6. Click **Preview**. The server compiles the snippet on the build worker and shows the resulting PDF in an iframe below the form. If the compile fails, an error block appears below the form with the relevant lines of the arara log so you can fix the issue and try again.
7. Once the preview compiles cleanly, click **Save & submit for review**. The example moves to **Pending review** and an admin will look at it.

Editing the form after a successful preview marks the preview stale; the **Save & submit for review** button is disabled until you click **Preview** again. (The same check is enforced server-side, so a stale preview cannot accidentally be submitted.)

### Lifecycle

| State | Meaning |
|---|---|
| **Draft** | You have saved an example but not submitted it. Visible only to you. |
| **Pending review** | Submitted, waiting for an admin. You cannot edit a pending example — wait for approval or rejection. |
| **Published** | Approved by an admin. Visible on `/examples` and on each tagged chapter's detail page; eligible for inclusion in book builds. After publication, the original author can still click **Edit (re-review)** to submit a correction — saving sends the example back to **Pending review** so an admin re-approves the new revision before it returns to the public listing. |
| **Rejected** | An admin asked for changes. The rejection reason appears at the top of the editor. Editing the example moves it back to **Draft** with the reason cleared, so you can iterate and re-submit. |

### Batch Import

Anyone with an account can upload multiple examples at once as a single zip, provided an administrator has enabled author batch imports (a **Batch import…** button appears next to **Submit an example** on `/examples` when the feature is on). The same workflow is always available to administrators under the admin panel at **Admin → Examples → Import**.

**Zip layout.** The archive must contain a `manifest.json` at its root plus one directory per example:

```
batch.zip
├── manifest.json
└── ex001/
    ├── statement.tex
    ├── solution.tex
    └── figures/          (optional)
        ├── fig1.pdf
        └── fig2.png
```

`manifest.json` is a JSON array, one entry per example:

```json
[
  {
    "dir": "ex001",
    "slug": "intro-rotation",
    "primary_chapter": "BASCRY",
    "chapters": ["BASCRY", "DIFCAL"],
    "difficulty": "standard"
  }
]
```

- `dir` *(required)* — directory name inside the zip.
- `primary_chapter` *(required)* — `chabbr` of the primary chapter. Must appear in `chapters`.
- `chapters` *(required)* — list of `chabbr` values the example is tagged to.
- `difficulty` — `introductory`, `standard`, or `advanced` (defaults to `standard`).
- `slug` *(optional)* — a stable per-author identifier. Re-importing the same `slug` updates the existing example rather than creating a duplicate, which makes the import idempotent across iterations.

Figure files must be `.pdf`, `.png`, or `.jpg/.jpeg`. The total archive size is capped at 50 MB and a single import is limited to 200 entries.

**Workflow.**

1. Click **Batch import…** on `/examples`.
2. Choose the **default status** for the import:
   - **Draft** — examples land in your personal drafts; you can review each one and submit them individually for review.
   - **Pending review** — examples skip the draft state and queue for admin review immediately.
   (Admins also see a **Published** option, which bypasses review.)
3. Pick the zip file and click **Validate**. The server parses the manifest, checks the chapter abbreviations, figure formats, and per-entry well-formedness, and returns a per-entry report. Nothing is written to the database during this step.
4. If the report shows no blocking errors, click **Confirm and import**. The commit runs in a single transaction; if anything fails, no rows are created. Successful entries appear in **My worked examples** (under the chosen status) and, if marked Pending review, in the admin queue.

### Where Examples Appear

- **`/examples`** — public browse with filters.
- **Each chapter detail page** — a "Worked examples" panel listing up to five tagged examples with a "Browse all →" link.
- **Inside a book build** — when you build a book that contains a chapter with tagged examples, the build pipeline appends a "Worked examples" section to that chapter (controlled by the per-build flags in [Building Your Book](#building-your-book)).

## Managing Your Books

The **My Books** page (accessible from the navigation bar) lists all your books with their current status:

| Status | Color | Meaning |
|---|---|---|
| draft | gray | Book is being assembled |
| queued | yellow | Build is queued |
| building | blue | Build in progress |
| complete | green | PDF ready |
| failed | red | Build failed |

From this page you can:

- Click a book title to open it in the Book Editor
- Click **Status** on building/queued books to view progress
- Click **Delete** to remove a book permanently

## Your Profile

Click **Profile** in the top-right corner of the navigation bar to view and manage your account.

The profile page shows:
- Your full name (click **Edit** to change it)
- Your email address
- Account creation date
- Last login date
- Staff role (if applicable)

### Visibility

The **Visibility** section controls whether your completed books appear in the public [Community Library](#community-library).

- Off (default): nothing about your books is exposed publicly.
- On: every book you have built (and every future build) is listed on `/community` with its title, parts, and chapter list. Your full name, if you have set one, is shown as the author; otherwise the entry is attributed to **Anonymous**. Your email is never shown. PDFs and HTML downloads remain private.

You can toggle the setting at any time. Turning it off removes all your books from the community page immediately.

### My Worked Examples

A **My worked examples** section lists every [example](#worked-examples) you have created, grouped by status (Drafts, Rejected, Pending review, Published). Each entry shows the example id, the primary chapter, and a one-line preview of the statement. Drafts and rejected entries link to the editor so you can iterate; pending and published entries open the public detail page.

Click **+ New example** at the top of the section to start a new submission.

### Changing Your Password

1. On the profile page, click **Change password**.
2. Enter your current password.
3. Enter your new password (minimum 8 characters) and confirm it.
4. Click **Update password**.

### Deleting Your Account

At the bottom of the profile page is a **Danger zone** section:

1. Click **Delete my account**.
2. Confirm twice (this action is permanent).
3. Your account and all associated data (books, builds) will be permanently removed.
4. You will be signed out and redirected to the home page.

## Resetting Your Password

If you forget your password:

1. On the sign-in page, click **Forgot password?**
2. Enter your email address and click **Send reset link**.
3. Check your email for a message from OpenChapters with a reset link.
4. Click the link in the email (or paste it into your browser).
5. Enter your new password and confirm it.
6. Click **Reset password**.
7. You will be redirected to the sign-in page.

**Notes:**
- Reset links expire after 3 days.
- If you don't receive the email, check your spam folder.
- In development mode (no SMTP server configured), the reset link is logged to the server console instead of being emailed.

## Feature Requests and Bug Reports

If you have an idea for a new feature or want to report a problem, please open an issue on the project's GitHub repository:

1. Go to [OpenChapters/OCwebdesign Issues](https://github.com/OpenChapters/OCwebdesign/issues).
2. Click **New issue**.
3. Choose a descriptive title and explain your suggestion or the problem you encountered.
4. Click **Submit new issue**.

A GitHub account (free) is required. The development team reviews all submissions and will follow up in the issue thread.
