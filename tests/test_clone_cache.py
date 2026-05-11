"""Tests for the warm-clone cache helpers in books/tasks.py.

Exercise _refresh_cache (clone vs fetch path), the cache-dir naming,
and the materialize-via-cache flow end-to-end with a local "remote"
so no network is involved.
"""

import subprocess
from pathlib import Path

import pytest

from books.tasks import (
    _cache_dir_for_repo,
    _materialize_via_cache,
    _refresh_cache,
)


@pytest.fixture
def log_collector():
    lines: list[str] = []
    return lines, lines.append


@pytest.fixture
def local_remote(tmp_path: Path) -> Path:
    """Create a tiny bare-style git remote in tmp_path and return its
    file:// URL. Lets us exercise the actual `git fetch` / `git clone`
    code paths in tests without hitting GitHub."""
    src = tmp_path / "upstream-src"
    src.mkdir()
    (src / "README.md").write_text("hello\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(src)], check=True)
    subprocess.run(["git", "-C", str(src), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(src), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(src), "add", "."], check=True)
    subprocess.run(["git", "-C", str(src), "commit", "-q", "-m", "v1"], check=True)
    return src


class TestCacheDirNaming:
    def test_slash_flattened(self, settings, tmp_path):
        settings.GIT_CACHE_DIR = str(tmp_path)
        d = _cache_dir_for_repo("OpenChapters/OpenChapters")
        assert d == tmp_path / "OpenChapters__OpenChapters"


class TestRefreshCache:
    def test_first_call_clones(self, settings, tmp_path, local_remote, log_collector):
        settings.GIT_CACHE_DIR = str(tmp_path / "cache")
        cache = tmp_path / "cache" / "x"
        _, log_fn = log_collector
        _refresh_cache(f"file://{local_remote}", cache, log_fn)
        assert (cache / ".git").is_dir()
        assert (cache / "README.md").read_text() == "hello\n"

    def test_second_call_fetches_updates(self, settings, tmp_path, local_remote, log_collector):
        settings.GIT_CACHE_DIR = str(tmp_path / "cache")
        cache = tmp_path / "cache" / "x"
        _, log_fn = log_collector
        _refresh_cache(f"file://{local_remote}", cache, log_fn)

        # Push a new commit upstream
        (local_remote / "README.md").write_text("hello v2\n")
        subprocess.run(["git", "-C", str(local_remote), "commit", "-aqm", "v2"], check=True)

        _refresh_cache(f"file://{local_remote}", cache, log_fn)
        assert (cache / "README.md").read_text() == "hello v2\n"

    def test_corrupted_cache_self_heals(self, settings, tmp_path, local_remote, log_collector):
        """Wipe the .git/objects directory mid-life — the next refresh
        should detect the breakage and re-clone from scratch."""
        settings.GIT_CACHE_DIR = str(tmp_path / "cache")
        cache = tmp_path / "cache" / "x"
        _, log_fn = log_collector
        _refresh_cache(f"file://{local_remote}", cache, log_fn)

        # Break the cache by clearing its objects dir but leaving .git/
        # in place so the "non-empty" check still passes.
        import shutil
        shutil.rmtree(cache / ".git" / "objects")
        (cache / ".git" / "objects").mkdir()

        # Should recover by re-cloning.
        _refresh_cache(f"file://{local_remote}", cache, log_fn)
        assert (cache / "README.md").is_file()


class TestMaterializeViaCache:
    def test_workspace_gets_hardlinked_copy(self, settings, tmp_path, local_remote, log_collector):
        settings.GIT_CACHE_DIR = str(tmp_path / "cache")
        target = tmp_path / "workspace" / "x"
        _, log_fn = log_collector

        _materialize_via_cache(f"file://{local_remote}", "owner/x", target, log_fn)
        assert target.is_dir()
        assert (target / "README.md").read_text() == "hello\n"

        cache = _cache_dir_for_repo("owner/x")
        # Hardlink check: inode equality on Linux.
        st_cache = (cache / "README.md").stat()
        st_target = (target / "README.md").stat()
        assert st_cache.st_ino == st_target.st_ino, (
            "expected hardlink — cache and target should share inodes"
        )

    def test_target_dir_replaced_if_present(self, settings, tmp_path, local_remote, log_collector):
        settings.GIT_CACHE_DIR = str(tmp_path / "cache")
        target = tmp_path / "workspace" / "x"
        target.mkdir(parents=True)
        (target / "stale-file").write_text("delete me")
        _, log_fn = log_collector

        _materialize_via_cache(f"file://{local_remote}", "owner/x", target, log_fn)
        assert not (target / "stale-file").exists()
        assert (target / "README.md").is_file()

    def test_two_calls_pick_up_upstream_change(self, settings, tmp_path, local_remote, log_collector):
        """Cache refresh path: second materialize sees the new commit."""
        settings.GIT_CACHE_DIR = str(tmp_path / "cache")
        target = tmp_path / "workspace" / "x"
        _, log_fn = log_collector

        _materialize_via_cache(f"file://{local_remote}", "owner/x", target, log_fn)
        assert (target / "README.md").read_text() == "hello\n"

        (local_remote / "README.md").write_text("hello v2\n")
        subprocess.run(["git", "-C", str(local_remote), "commit", "-aqm", "v2"], check=True)

        _materialize_via_cache(f"file://{local_remote}", "owner/x", target, log_fn)
        assert (target / "README.md").read_text() == "hello v2\n"
