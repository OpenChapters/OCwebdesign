"""Chapter dependency resolution.

The catalog distinguishes two kinds of cross-chapter links (see the
``Chapter`` model):

* ``depends_on`` — FOUNDATIONAL prerequisites. Hard: a book that includes a
  chapter must also include everything in the transitive closure of its
  ``depends_on``, so that cross-chapter ``\\label``/``\\ref`` resolve. These are
  auto-included by the build pipeline into a prepended "Foundations" part.
* ``related_to`` — TOPICAL cross-references. Soft: surfaced as a frontend
  suggestion only and resolved there; this module does NOT touch ``related_to``.

``resolve_foundational_dependencies`` computes the foundational chapters that
must be added to satisfy a book's ``depends_on`` closure, in topological order
(a prerequisite's prerequisite precedes it). It is the single source of truth
shared by ``books.tasks._build_request_data`` and
``books.views.BookExamplesAvailableView``.
"""

from collections.abc import Iterable

from catalog.models import Chapter


def resolve_foundational_dependencies(
    included_chabbrs: set[str],
    seed_depends_on: Iterable[str],
) -> list[Chapter]:
    """Return the foundational chapters to add to satisfy a book's deps.

    Args:
        included_chabbrs: chabbr values already present in the book. Targets in
            this set are treated as satisfied and skipped (but their own deps
            are still pulled in if not present).
        seed_depends_on: the flattened ``depends_on`` lists of every chapter
            already in the book — the roots of the dependency walk.

    Returns:
        Published foundational ``Chapter`` objects in topological order: if FC1
        lists FC2 in its ``depends_on``, FC2 precedes FC1. Already-included,
        missing, and unpublished targets are dropped. Deterministic across runs
        (ties broken by title). Cycle-safe — a dependency cycle terminates
        without looping and each chapter still appears exactly once.
    """
    # Single bulk load of the (small) published-chapter graph — avoids per-hop
    # queries and the N+1 the call sites used to incur.
    published = (
        Chapter.objects.filter(published=True)
        .only(
            "id", "chabbr", "title", "depends_on",
            "github_repo", "chapter_subdir", "latex_entry_file",
        )
    )
    by_chabbr: dict[str, Chapter] = {c.chabbr: c for c in published if c.chabbr}

    def title_of(chabbr: str) -> str:
        ch = by_chabbr.get(chabbr)
        return ch.title if ch is not None else chabbr

    result: list[Chapter] = []
    permanent: set[str] = set()   # fully processed (placed or deliberately skipped)
    visiting: set[str] = set()    # on the current DFS stack — cycle guard

    def visit(chabbr: str) -> None:
        if chabbr in permanent:
            return
        if chabbr in included_chabbrs:
            permanent.add(chabbr)   # already in the book; nothing to add
            return
        if chabbr in visiting:
            return                  # back-edge: cycle, stop descending
        ch = by_chabbr.get(chabbr)
        if ch is None:
            permanent.add(chabbr)   # missing or unpublished target — drop
            return
        visiting.add(chabbr)
        # Recurse into this chapter's own prerequisites first so they land
        # before it (post-order ⇒ topological order).
        for dep in sorted(ch.depends_on, key=title_of):
            visit(dep)
        visiting.discard(chabbr)
        permanent.add(chabbr)
        result.append(ch)

    for chabbr in sorted(set(seed_depends_on), key=title_of):
        visit(chabbr)

    return result
