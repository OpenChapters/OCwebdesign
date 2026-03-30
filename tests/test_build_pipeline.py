"""Tests for the build pipeline validation and helper functions."""

import pytest

from books.tasks import _build_request_data, _validate_build_data
from tests.factories import BookChapterFactory, BookFactory, BookPartFactory, ChapterFactory


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
