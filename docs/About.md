# About the OpenChapters Project

This project consists of a web application for building on-demand, open-source PDF textbooks from LaTeX source chapters. Authors contribute chapters under the [Creative Commons CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) license, and maintain their own chapter(s) using a central GitHub repository. Course instructors who wish to configure their own custom textbook can browse the catalog, assemble custom books, and receive professionally typeset PDFs.

## How It Works

After creating a user account, a user can:

1. **Browse** — explore the chapter catalog with hover-to-preview tables of contents
2. **Assemble** — create a book, organize chapters into parts, drag-and-drop to reorder
3. **Build** — submit the book for LaTeX typesetting using the TeXLive distribution; the server clones chapter sources, runs the [arara](https://github.com/islandoftex/arara) build pipeline, and produces a PDF
4. **Download** — completed PDFs appear in your personal library and will persist there long term; the Build data is stored and a user can return to a book at any point, modify it, and re-build it

Chapters and figures live in the [OpenChapters/OpenChapters](https://github.com/OpenChapters/OpenChapters) monorepo on GitHub. The chapter catalog is synced nightly so that the latest version of all chapters is always available.

## Contributing a New Chapter

A chapter template is available from the [OpenChapters/OCchaptertemplate](https://github.com/OpenChapters/OCchaptertemplate) repository. If you want to contribute a chapter, please follow these steps:

1. **Fork** the [OpenChapters/OCchaptertemplate](https://github.com/OpenChapters/OCchaptertemplate) repository to your GitHub account, then **clone** it to your local machine
2. **Read** the AuthorInstructions.pdf file that comes with the repository; this document explains all the style conventions that need to be followed for each chapter
3. **Write** your chapter and commit/push all changes into your forked ChapterTemplate repository
4. **Submit** a pull request to the OpenChapters repository when you have a completed chapter; an editor will review your contribution and interact with you to resolve any potential formatting issues before making the chapter available on the active [OpenChapters/OpenChapters](https://github.com/OpenChapters/OpenChapters) repository
5. **Update** your chapter on a regular basis and submit a pull request for each update

**Important Notice:** an open source book project like this one can only survive long term if all authors strictly adhere to the rule that *only material that falls under the [Creative Commons CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) license can be used.*  This means that existing figures that fall under copyright from any publisher **will not be allowed**; all figures used **must** be new figures.

## Project Funding

The OpenChapters project started with partial financial support from a Vannevar Bush Faculty Fellowship program (ONR # N00014-16-1-2821), and was continued with partial funding from an NSF research program DMR \#1904629. Current development is carried out with support from NSF grant DMR-2203378. MDG would like to acknowledge support from the John and Claire Bertucci Distinguished Professorship in Engineering.


## License

Content (chapters, figures) is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
