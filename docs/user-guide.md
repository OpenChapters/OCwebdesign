# OpenChapters User Guide

OpenChapters is a free, open-source platform for building custom PDF textbooks from a library of LaTeX-typeset chapters. This guide walks you through every step, from creating an account to downloading your finished book.

---

## Table of Contents

1. [Creating an Account](#creating-an-account)
2. [Signing In](#signing-in)
3. [Browsing Chapters](#browsing-chapters)
4. [Searching Chapter Content](#searching-chapter-content)
5. [Reading a Chapter Online](#reading-a-chapter-online)
6. [Chapter Details](#chapter-details)
7. [Creating a Book](#creating-a-book)
8. [The Book Editor](#the-book-editor)
   - [Adding Parts](#adding-parts)
   - [Adding Chapters](#adding-chapters)
   - [Reordering Chapters](#reordering-chapters)
   - [Reordering Parts](#reordering-parts)
   - [Moving Chapters Between Parts](#moving-chapters-between-parts)
   - [Removing Chapters and Parts](#removing-chapters-and-parts)
   - [Auto-Include Foundational Chapters](#auto-include-foundational-chapters)
9. [Building Your Book](#building-your-book)
10. [Build Status](#build-status)
11. [Your Library](#your-library)
12. [Managing Your Books](#managing-your-books)
13. [Your Profile](#your-profile)
14. [Resetting Your Password](#resetting-your-password)
15. [Feature Requests and Bug Reports](#feature-requests-and-bug-reports)

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

## Searching Chapter Content

Click **Search** in the top navigation bar to open the full-text search page. Type a query and results appear as you type:

- Each result shows the chapter, the section heading that contains the match, and a short snippet with the matching term(s) highlighted in yellow.
- Supports phrases in quotes (`"rotation matrix"`), required terms (`+quaternion euler`), and boolean OR.
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

1. Click the **Build PDF** button in the top-right corner of the Book Editor.
2. Confirm the build in the dialog.
3. You will be redirected to the Build Status page.

The build process typically takes 1–3 minutes depending on the number of chapters and figures. During a build, the server:

- Clones the chapter source files from GitHub
- Merges bibliographies and collects figures
- Typesets the book using LaTeX (pdflatex + biber + makeindex)
- Produces a professionally formatted PDF

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

If the build **succeeds**, a **Download PDF** button appears. If email delivery is configured on the server, you will also receive an email with a download link that remains valid for 7 days. If the build **fails**, the error message from the LaTeX log is shown to help diagnose the issue.

## Your Library

Click **Library** in the navigation bar to see all your completed books. Each entry shows:

- Book title
- Completion date
- A **Build info** link to view the build status
- A **Download PDF** button to download the book directly

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
