"""Tests for the build pipeline validation and helper functions."""

import pytest

from books.tasks import _build_request_data, _validate_build_data
from tests.factories import (
    BookChapterFactory,
    BookFactory,
    BookPartFactory,
    ChapterFactory,
    FoundationalChapterFactory,
)


@pytest.mark.django_db
class TestBuildRequestData:
    def test_serializes_book_structure(self):
        book = BookFactory()
        part = BookPartFactory(book=book, title="Part I", order=0)
        ch = ChapterFactory(
            github_repo="OpenChapters/OpenChapters",
            chapter_subdir="src/LinearAlgebra",
            latex_entry_file="src/LinearAlgebra/LinearAlgebra.tex",
        )
        BookChapterFactory(part=part, chapter=ch, order=0)

        data = _build_request_data(book)
        assert data["book_title"] == book.title
        assert len(data["parts"]) == 1
        assert data["parts"][0]["title"] == "Part I"
        assert len(data["parts"][0]["chapters"]) == 1
        assert data["parts"][0]["chapters"][0]["repo"] == "OpenChapters/OpenChapters"

    def test_empty_book(self):
        book = BookFactory()
        data = _build_request_data(book)
        assert data["parts"] == []

    def test_auto_includes_foundational_dependencies(self):
        """Foundational chapters listed in depends_on are auto-included."""
        fc = FoundationalChapterFactory(
            chabbr="LINALG",
            github_repo="OpenChapters/OpenChapters",
            chapter_subdir="src/LinearAlgebra",
            latex_entry_file="src/LinearAlgebra/LinearAlgebra.tex",
        )
        tc = ChapterFactory(
            depends_on=["LINALG"],
            github_repo="OpenChapters/OpenChapters",
            chapter_subdir="src/Diffraction",
            latex_entry_file="src/Diffraction/Diffraction.tex",
        )
        book = BookFactory()
        part = BookPartFactory(book=book, title="Topics", order=0)
        BookChapterFactory(part=part, chapter=tc, order=0)

        data = _build_request_data(book)

        # Should have two parts: auto-inserted Foundations + user's Topics
        assert len(data["parts"]) == 2
        assert data["parts"][0]["title"] == "Foundations"
        assert len(data["parts"][0]["chapters"]) == 1
        assert data["parts"][0]["chapters"][0]["entry_file"] == fc.latex_entry_file
        assert data["parts"][1]["title"] == "Topics"

    def test_no_duplicate_when_dependency_already_included(self):
        """If the user already added a foundational chapter, don't duplicate it."""
        fc = FoundationalChapterFactory(
            chabbr="LINALG",
            github_repo="OpenChapters/OpenChapters",
            chapter_subdir="src/LinearAlgebra",
            latex_entry_file="src/LinearAlgebra/LinearAlgebra.tex",
        )
        tc = ChapterFactory(
            depends_on=["LINALG"],
            github_repo="OpenChapters/OpenChapters",
            chapter_subdir="src/Diffraction",
            latex_entry_file="src/Diffraction/Diffraction.tex",
        )
        book = BookFactory()
        part1 = BookPartFactory(book=book, title="Foundations", order=0)
        BookChapterFactory(part=part1, chapter=fc, order=0)
        part2 = BookPartFactory(book=book, title="Topics", order=1)
        BookChapterFactory(part=part2, chapter=tc, order=0)

        data = _build_request_data(book)

        # No auto-inserted part — dependency already present
        assert len(data["parts"]) == 2
        assert data["parts"][0]["title"] == "Foundations"
        assert data["parts"][1]["title"] == "Topics"

    def test_transitive_dependencies_resolved_in_topological_order(self):
        """depends_on is resolved to full transitive closure, with each
        prerequisite ordered before the chapter that requires it."""
        # CALC depends on LINALG; the topical chapter depends only on CALC.
        FoundationalChapterFactory(chabbr="LINALG", title="Linear Algebra")
        FoundationalChapterFactory(chabbr="CALC", title="Calculus", depends_on=["LINALG"])
        tc = ChapterFactory(depends_on=["CALC"])

        book = BookFactory()
        part = BookPartFactory(book=book, title="Topics", order=0)
        BookChapterFactory(part=part, chapter=tc, order=0)

        data = _build_request_data(book)

        assert len(data["parts"]) == 2
        foundation = data["parts"][0]
        assert foundation["title"] == "Foundations"
        # Both the direct (CALC) and transitive (LINALG) deps are present,
        # with LINALG before CALC since CALC depends on it.
        titles = [c["title"] for c in foundation["chapters"]]
        assert titles == ["Linear Algebra", "Calculus"]

    def test_diamond_dependency_included_once(self):
        """A dependency reachable by two paths appears exactly once."""
        FoundationalChapterFactory(chabbr="BASE", title="Base")
        FoundationalChapterFactory(chabbr="A", title="A", depends_on=["BASE"])
        FoundationalChapterFactory(chabbr="B", title="B", depends_on=["BASE"])
        tc = ChapterFactory(depends_on=["A", "B"])

        book = BookFactory()
        part = BookPartFactory(book=book, title="Topics", order=0)
        BookChapterFactory(part=part, chapter=tc, order=0)

        data = _build_request_data(book)
        titles = [c["title"] for c in data["parts"][0]["chapters"]]
        assert titles.count("Base") == 1
        # BASE precedes both A and B.
        assert titles.index("Base") < titles.index("A")
        assert titles.index("Base") < titles.index("B")

    def test_dependency_cycle_terminates(self):
        """A depends_on cycle resolves without infinite recursion; each
        chapter in the cycle is included exactly once."""
        FoundationalChapterFactory(chabbr="X", title="X", depends_on=["Y"])
        FoundationalChapterFactory(chabbr="Y", title="Y", depends_on=["X"])
        tc = ChapterFactory(depends_on=["X"])

        book = BookFactory()
        part = BookPartFactory(book=book, title="Topics", order=0)
        BookChapterFactory(part=part, chapter=tc, order=0)

        data = _build_request_data(book)
        titles = [c["title"] for c in data["parts"][0]["chapters"]]
        assert sorted(titles) == ["X", "Y"]

    def test_unpublished_dependency_dropped(self):
        """A depends_on target that is unpublished is silently skipped."""
        FoundationalChapterFactory(chabbr="GONE", title="Gone", published=False)
        tc = ChapterFactory(depends_on=["GONE"])

        book = BookFactory()
        part = BookPartFactory(book=book, title="Topics", order=0)
        BookChapterFactory(part=part, chapter=tc, order=0)

        data = _build_request_data(book)
        # No Foundations part — the only dependency was unpublished.
        assert [p["title"] for p in data["parts"]] == ["Topics"]

    def test_related_to_not_auto_included(self):
        """related_to is a soft cross-reference: never auto-included in builds."""
        FoundationalChapterFactory(chabbr="OTHER", title="Other Topic")
        tc = ChapterFactory(related_to=["OTHER"])

        book = BookFactory()
        part = BookPartFactory(book=book, title="Topics", order=0)
        BookChapterFactory(part=part, chapter=tc, order=0)

        data = _build_request_data(book)
        # related_to has no build-time effect — only the Topics part exists.
        assert [p["title"] for p in data["parts"]] == ["Topics"]


class TestBuildDataValidation:
    def test_valid_data_passes(self):
        data = {
            "book_title": "Test",
            "parts": [{
                "title": "Part I",
                "chapters": [{
                    "repo": "OpenChapters/OpenChapters",
                    "chapter_subdir": "src/LinearAlgebra",
                    "entry_file": "src/LinearAlgebra/LinearAlgebra.tex",
                }],
            }],
        }
        _validate_build_data(data)  # should not raise

    def test_invalid_repo_name(self):
        data = {
            "parts": [{"chapters": [{"repo": "evil;rm -rf /", "chapter_subdir": "src/X", "entry_file": "x.tex"}]}],
        }
        with pytest.raises(ValueError, match="Invalid repo name"):
            _validate_build_data(data)

    def test_path_traversal_in_subdir(self):
        data = {
            "parts": [{"chapters": [{"repo": "A/B", "chapter_subdir": "../../etc/passwd", "entry_file": "x.tex"}]}],
        }
        with pytest.raises(ValueError, match="Invalid chapter_subdir"):
            _validate_build_data(data)

    def test_path_traversal_in_entry_file(self):
        data = {
            "parts": [{"chapters": [{"repo": "A/B", "chapter_subdir": "src/X", "entry_file": "../../etc/shadow"}]}],
        }
        with pytest.raises(ValueError, match="Invalid entry_file"):
            _validate_build_data(data)

    def test_shell_metacharacters_in_repo(self):
        data = {
            "parts": [{"chapters": [{"repo": "A/B$(whoami)", "chapter_subdir": "src/X", "entry_file": "x.tex"}]}],
        }
        with pytest.raises(ValueError, match="Invalid repo name"):
            _validate_build_data(data)

    def test_empty_parts_passes(self):
        data = {"parts": []}
        _validate_build_data(data)  # should not raise

    def test_empty_chapters_passes(self):
        data = {"parts": [{"chapters": []}]}
        _validate_build_data(data)  # should not raise
