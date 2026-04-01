"""
Backwards-compatible wrapper around the pluggable git provider.

All functions delegate to ``catalog.git_provider.get_provider()``.
New code should import from ``catalog.git_provider`` directly.

Existing call sites (sync_chapters, admin views) continue to work
without changes.
"""

from catalog.git_provider import DEFAULT_CHAPTERS_REPO, DEFAULT_SRC_PATH, get_provider


def list_chapter_subdirs(
    repo: str = DEFAULT_CHAPTERS_REPO,
    src_path: str = DEFAULT_SRC_PATH,
) -> list[str]:
    return get_provider().list_chapter_subdirs(repo, src_path)


def fetch_chapter_json(repo: str, path: str) -> dict | None:
    return get_provider().fetch_chapter_json(repo, path)


def raw_file_url(repo: str, branch: str, path: str) -> str:
    return get_provider().raw_file_url(repo, branch, path)


def clone_url(repo: str) -> str:
    return get_provider().clone_url(repo)
