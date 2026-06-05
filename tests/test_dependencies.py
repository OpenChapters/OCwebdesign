"""Unit tests for the foundational-dependency resolver.

Exercises catalog.services.dependencies.resolve_foundational_dependencies
directly (independent of the build pipeline / examples view that consume it).
"""

import pytest

from catalog.services.dependencies import resolve_foundational_dependencies
from tests.factories import FoundationalChapterFactory


def _titles(chapters):
    return [c.title for c in chapters]


@pytest.mark.django_db
class TestResolveFoundationalDependencies:
    def test_linear_chain_topological_order(self):
        """A→B→C resolves to all three, deepest prerequisite first."""
        FoundationalChapterFactory(chabbr="C", title="C")
        FoundationalChapterFactory(chabbr="B", title="B", depends_on=["C"])
        FoundationalChapterFactory(chabbr="A", title="A", depends_on=["B"])

        result = resolve_foundational_dependencies(set(), ["A"])

        assert _titles(result) == ["C", "B", "A"]

    def test_diamond_appears_once(self):
        """A shared dependency reachable via two paths is returned once."""
        FoundationalChapterFactory(chabbr="BASE", title="Base")
        FoundationalChapterFactory(chabbr="L", title="L", depends_on=["BASE"])
        FoundationalChapterFactory(chabbr="R", title="R", depends_on=["BASE"])

        result = resolve_foundational_dependencies(set(), ["L", "R"])

        titles = _titles(result)
        assert titles.count("Base") == 1
        assert titles.index("Base") < titles.index("L")
        assert titles.index("Base") < titles.index("R")

    def test_cycle_terminates_and_includes_each_once(self):
        FoundationalChapterFactory(chabbr="X", title="X", depends_on=["Y"])
        FoundationalChapterFactory(chabbr="Y", title="Y", depends_on=["X"])

        result = resolve_foundational_dependencies(set(), ["X"])

        assert sorted(_titles(result)) == ["X", "Y"]

    def test_already_included_target_not_readded(self):
        """A referenced chapter that is already in the book is not returned."""
        FoundationalChapterFactory(chabbr="MID", title="Mid")
        result = resolve_foundational_dependencies({"MID"}, ["MID"])
        assert result == []

    def test_transitive_dep_of_in_book_chapter_pulled(self):
        """A dep of an in-book chapter that is NOT itself in the book is pulled
        in. Per the caller contract, the seed is the in-book chapter's
        depends_on (here MID's ["DEEP"]), so DEEP is reached even though MID
        itself is already included."""
        FoundationalChapterFactory(chabbr="DEEP", title="Deep")
        FoundationalChapterFactory(chabbr="MID", title="Mid", depends_on=["DEEP"])
        result = resolve_foundational_dependencies({"MID"}, ["DEEP"])
        assert _titles(result) == ["Deep"]

    def test_missing_target_dropped(self):
        result = resolve_foundational_dependencies(set(), ["NOPE"])
        assert result == []

    def test_unpublished_target_dropped(self):
        FoundationalChapterFactory(chabbr="GONE", title="Gone", published=False)
        result = resolve_foundational_dependencies(set(), ["GONE"])
        assert result == []

    def test_title_tiebreak_is_deterministic(self):
        """Independent roots come out in a stable, title-sorted order."""
        FoundationalChapterFactory(chabbr="ONE", title="Zebra")
        FoundationalChapterFactory(chabbr="TWO", title="Apple")

        result = resolve_foundational_dependencies(set(), ["ONE", "TWO"])

        assert _titles(result) == ["Apple", "Zebra"]
