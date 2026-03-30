"""
GitHub API client for fetching OpenChapters chapter metadata.

Chapters live in a monorepo (OpenChapters/OpenChapters) under src/.
Each subdirectory of src/ is one chapter and may contain a chapter.json
metadata file at its root.

All functions use a short-lived httpx.Client so they are safe to call from
both management commands (synchronous) and Celery tasks (synchronous worker
thread).  Authentication uses the GITHUB_TOKEN setting; without a token the
GitHub API allows only 60 unauthenticated requests per hour.

Transient failures (5xx, timeouts) are retried up to 3 times with
exponential backoff.
"""

import base64
import json
import logging
import time

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.github.com"
DEFAULT_CHAPTERS_REPO = "OpenChapters/OpenChapters"
DEFAULT_SRC_PATH = "src"

_MAX_RETRIES = 3
_RETRY_BACKOFF = 2  # seconds; doubles each retry


def _headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = getattr(settings, "GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request_with_retry(method: str, url: str, **kwargs) -> httpx.Response:
    """Make an HTTP request with retry on transient failures."""
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            with httpx.Client(headers=_headers(), timeout=30) as client:
                resp = getattr(client, method)(url, **kwargs)
                # Retry on server errors (500, 502, 503)
                if resp.status_code >= 500:
                    logger.warning(
                        "GitHub %d on %s (attempt %d/%d)",
                        resp.status_code, url, attempt + 1, _MAX_RETRIES,
                    )
                    if attempt < _MAX_RETRIES - 1:
                        time.sleep(_RETRY_BACKOFF * (2 ** attempt))
                        continue
                return resp
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exc = exc
            logger.warning(
                "GitHub %s on %s (attempt %d/%d)",
                type(exc).__name__, url, attempt + 1, _MAX_RETRIES,
            )
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BACKOFF * (2 ** attempt))
    raise last_exc or httpx.ConnectError("Failed after retries")


def list_chapter_subdirs(
    repo: str = DEFAULT_CHAPTERS_REPO,
    src_path: str = DEFAULT_SRC_PATH,
) -> list[str]:
    """
    Return the names of all subdirectories under *src_path* in *repo*.

    Each subdirectory is expected to be one chapter.  The returned names are
    bare directory names (e.g. ``"LinearAlgebra"``), not full paths.
    """
    url = f"{_BASE_URL}/repos/{repo}/contents/{src_path}"
    resp = _request_with_retry("get", url)
    resp.raise_for_status()
    items = resp.json()

    dirs = [item["name"] for item in items if item["type"] == "dir"]
    logger.debug("list_chapter_subdirs(%s, %s): %d dirs", repo, src_path, len(dirs))
    return dirs


def fetch_chapter_json(repo: str, path: str) -> dict | None:
    """
    Fetch and parse ``chapter.json`` at *path* within *repo*.

    *path* is the full path from the repo root, e.g.
    ``"src/LinearAlgebra/chapter.json"``.

    Returns the parsed dict on success, or ``None`` if the file does not
    exist (HTTP 404).  Raises ``httpx.HTTPStatusError`` for other failures.
    """
    url = f"{_BASE_URL}/repos/{repo}/contents/{path}"
    resp = _request_with_retry("get", url)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()

    raw = base64.b64decode(data["content"]).decode("utf-8")
    return json.loads(raw)


def raw_file_url(repo: str, branch: str, path: str) -> str:
    """
    Build a ``raw.githubusercontent.com`` URL for *path* inside *repo*.

    Example::

        raw_file_url("OpenChapters/OpenChapters", "master", "src/LinearAlgebra/cover.png")
        # → "https://raw.githubusercontent.com/OpenChapters/OpenChapters/master/src/LinearAlgebra/cover.png"
    """
    owner, repo_name = repo.split("/", 1)
    return f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/{path}"
