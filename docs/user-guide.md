# OpenChapters User Guide

OpenChapters is a free, open-source platform for building custom PDF textbooks from a library of LaTeX-typeset chapters. This guide walks you through every step, from creating an account to downloading your finished book.

---

## Table of Contents

1. [Creating an Account](#creating-an-account)
2. [Browsing Chapters](#browsing-chapters)
3. [Chapter Details](#chapter-details)
4. [Creating a Book](#creating-a-book)
5. [The Book Editor](#the-book-editor)
   - [Adding Parts](#adding-parts)
   - [Adding Chapters](#adding-chapters)
   - [Reordering Chapters](#reordering-chapters)
   - [Moving Chapters Between Parts](#moving-chapters-between-parts)
   - [Removing Chapters and Parts](#removing-chapters-and-parts)
   - [Auto-Include Foundational Chapters](#auto-include-foundational-chapters)
6. [Building Your Book](#building-your-book)
7. [Build Status](#build-status)
8. [Your Library](#your-library)
9. [Managing Your Books](#managing-your-books)

---

## Creating an Account

1. Click **Register** in the top-right corner of the navigation bar.
2. Enter your email address and choose a password (minimum 8 characters).
3. Click **Create account**.
4. You will be redirected to the sign-in page. Enter your credentials to log in.

Your email address is your login identifier and will be used for PDF delivery notifications in the future.

## Browsing Chapters

The **Chapter Browser** is the main page of the site, accessible by clicking **Browse** in the navigation bar or visiting the home page.

Chapters are organized into two sections:

- **Topical Chapters** — specialized topics in materials science and engineering (displayed first)
- **Foundational Chapters** — core mathematical and scientific background

Each chapter is displayed as a card showing:
- Chapter title
- Author(s)
- Keywords (if available)
- A cover image or placeholder icon

### Searching

Use the search box in the top-right corner to filter chapters by title, author, or keyword. The search applies across both topical and foundational sections.

### Hover Preview

Hover your mouse over any chapter card to see a **table of contents** popover listing the sections within that chapter. This lets you quickly assess whether a chapter covers the topics you need.

## Chapter Details

Each chapter card has two buttons:

- **View** — opens the full chapter detail page showing:
  - Complete table of contents
  - Author(s) and description
  - Keywords
  - Chapter type (foundational or topical)
  - Dependencies on other foundational chapters
  - An **+ Add to Book** button

- **+ Add to Book** — opens the chapter detail page with the book picker already visible. You can:
  - Select an existing draft book to add the chapter to
  - Click **+ Create new book** to start a new book with this chapter

When you add a chapter from the detail page, it is placed in the first part of the chosen book. You can rearrange it later in the Book Editor.

## Creating a Book

There are two ways to create a new book:

### From the Chapter Browser
Click **+ Add to Book** on any chapter card, then choose **+ Create new book**. A new book titled "Untitled Book" is created with the selected chapter already added.

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
- Click **Dismiss** to hide the banner (the book will still build, but cross-references to missing chapters will be unresolved)

Foundational chapters are added to the first part of your book. You can move them to a different part afterward.

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

If the build **succeeds**, the PDF file path is displayed. If it **fails**, the error message from the LaTeX log is shown to help diagnose the issue.

## Your Library

Click **Library** in the navigation bar to see all your completed books. Each entry shows:

- Book title
- Completion date
- A link to view the build status and PDF location

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
