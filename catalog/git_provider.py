"""
Pluggable git provider abstraction for fetching chapter metadata.

Supports GitHub and GitLab. The active provider is selected by the
GIT_PROVIDER setting ("github" or "gitlab"). All chapter sync, TOC
updates, thumbnail updates, and build pipeline operations use this
module instead of calling GitHub APIs directly.

Usage::

    from catalog.git_provider import get_provider

    provider = get_provider()
    subdirs = provider.list_chapter_subdirs("OpenChapters/OpenChapters", "src")
    data = provider.fetch_chapter_json("OpenChapters/OpenChapters", "src/LinearAlgebra/chapter.json")
    url = provider.raw_file_url("OpenChapters/OpenChapters", "master", "src/LinearAlgebra/cover.png")
    clone_url = provider.clone_url("OpenChapters/OpenChapters")
"""

import abc
import base64
import json
import logging
import time
from urllib.parse import quote as urlquote

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF = 2  # seconds; doubles each retry

DEFAULT_CHAPTERS_REPO = "OpenChapters/OpenChapters"
DEFAULT_SRC_PATH = "src"


def _request_with_retry(method: str, url: str, headers: dict, **kwargs) -> httpx.Response:
    """Make an HTTP request with retry on transient failures (5xx, timeouts)."""
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            with httpx.Client(headers=headers, timeout=30) as client:
                resp = getattr(client, method)(url, **kwargs)
                if resp.status_code >= 500:
                    logger.warning(
                        "Git API %d on %s (attempt %d/%d)",
                        resp.status_code, url, attempt + 1, _MAX_RETRIES,
                    )
                    if attempt < _MAX_RETRIES - 1:
                        time.sleep(_RETRY_BACKOFF * (2 ** attempt))
                        continue
                return resp
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exc = exc
            logger.warning(
                "Git API %s on %s (attempt %d/%d)",
                type(exc).__name__, url, attempt + 1, _MAX_RETRIES,
            )
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BACKOFF * (2 ** attempt))
    raise last_exc or httpx.ConnectError("Failed after retries")


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class GitProvider(abc.ABC):
    """Abstract interface for a git hosting service."""

    @abc.abstractmethod
    def list_chapter_subdirs(self, repo: str, src_path: str) -> list[str]:
        """Return directory names under *src_path* in *repo*."""

    @abc.abstractmethod
    def fetch_chapter_json(self, repo: str, path: str) -> dict | None:
        """Fetch and parse chapter.json at *path*. Return None on 404."""

    @abc.abstractmethod
    def raw_file_url(self, repo: str, branch: str, path: str) -> str:
        """Return a public URL to the raw file content."""

    @abc.abstractmethod
    def clone_url(self, repo: str) -> str:
        """Return the HTTPS clone URL for *repo*."""

    @abc.abstractmethod
    def last_commit_date(self, repo: str, path: str) -> str | None:
        """Return the ISO-8601 date of the most recent commit touching *path*, or None."""


# ---------------------------------------------------------------------------
# GitHub implementation
# ---------------------------------------------------------------------------

class GitHubProvider(GitProvider):
    """GitHub API implementation."""

    BASE_URL = "https://api.github.com"

    def _headers(self) -> dict:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = getattr(settings, "GIT_TOKEN", "") or getattr(settings, "GITHUB_TOKEN", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def list_chapter_subdirs(self, repo: str, src_path: str) -> list[str]:
        url = f"{self.BASE_URL}/repos/{repo}/contents/{src_path}"
        resp = _request_with_retry("get", url, headers=self._headers())
        resp.raise_for_status()
        items = resp.json()
        dirs = [item["name"] for item in items if item["type"] == "dir"]
        logger.debug("GitHub list_chapter_subdirs(%s, %s): %d dirs", repo, src_path, len(dirs))
        return dirs

    def fetch_chapter_json(self, repo: str, path: str) -> dict | None:
        url = f"{self.BASE_URL}/repos/{repo}/contents/{path}"
        resp = _request_with_retry("get", url, headers=self._headers())
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        raw = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(raw)

    def raw_file_url(self, repo: str, branch: str, path: str) -> str:
        owner, repo_name = repo.split("/", 1)
        return f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/{path}"

    def clone_url(self, repo: str) -> str:
        return f"https://github.com/{repo}.git"

    def last_commit_date(self, repo: str, path: str) -> str | None:
        url = f"{self.BASE_URL}/repos/{repo}/commits"
        resp = _request_with_retry(
            "get", url, headers=self._headers(),
            params={"path": path, "per_page": 1},
        )
        if resp.status_code != 200:
            return None
        commits = resp.json()
        if not commits:
            return None
        return commits[0]["commit"]["committer"]["date"]


# ---------------------------------------------------------------------------
# GitLab implementation
# ---------------------------------------------------------------------------

class GitLabProvider(GitProvider):
    """
    GitLab API implementation.

    Requires GIT_BASE_URL (e.g., "https://gitlab.example.com") and
    GIT_TOKEN (a GitLab personal access token with read_repository scope).

    The *repo* parameter is the project path (e.g., "group/project"),
    which is URL-encoded for API calls.
    """

    def __init__(self):
        self.base_url = getattr(settings, "GIT_BASE_URL", "https://gitlab.com").rstrip("/")

    def _headers(self) -> dict:
        headers = {"Accept": "application/json"}
        token = getattr(settings, "GIT_TOKEN", "")
        if token:
            headers["PRIVATE-TOKEN"] = token
        return headers

    def _project_id(self, repo: str) -> str:
        """URL-encode the project path for GitLab API."""
        return urlquote(repo, safe="")

    def list_chapter_subdirs(self, repo: str, src_path: str) -> list[str]:
        pid = self._project_id(repo)
        url = f"{self.base_url}/api/v4/projects/{pid}/repository/tree"
        resp = _request_with_retry("get", url, headers=self._headers(), params={
            "path": src_path,
            "per_page": 100,
        })
        resp.raise_for_status()
        items = resp.json()
        dirs = [item["name"] for item in items if item["type"] == "tree"]
        logger.debug("GitLab list_chapter_subdirs(%s, %s): %d dirs", repo, src_path, len(dirs))
        return dirs

    def fetch_chapter_json(self, repo: str, path: str) -> dict | None:
        pid = self._project_id(repo)
        encoded_path = urlquote(path, safe="")
        url = f"{self.base_url}/api/v4/projects/{pid}/repository/files/{encoded_path}/raw"
        resp = _request_with_retry("get", url, headers=self._headers(), params={
            "ref": getattr(settings, "GIT_DEFAULT_BRANCH", "main"),
        })
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def raw_file_url(self, repo: str, branch: str, path: str) -> str:
        pid = self._project_id(repo)
        encoded_path = urlquote(path, safe="")
        return f"{self.base_url}/api/v4/projects/{pid}/repository/files/{encoded_path}/raw?ref={branch}"

    def clone_url(self, repo: str) -> str:
        return f"{self.base_url}/{repo}.git"

    def last_commit_date(self, repo: str, path: str) -> str | None:
        pid = self._project_id(repo)
        url = f"{self.base_url}/api/v4/projects/{pid}/repository/commits"
        resp = _request_with_retry(
            "get", url, headers=self._headers(),
            params={"path": path, "per_page": 1},
        )
        if resp.status_code != 200:
            return None
        commits = resp.json()
        if not commits:
            return None
        return commits[0]["committed_date"]


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "github": GitHubProvider,
    "gitlab": GitLabProvider,
}

_cached_provider: GitProvider | None = None


def get_provider() -> GitProvider:
    """Return the configured git provider instance (cached)."""
    global _cached_provider
    if _cached_provider is None:
        provider_name = getattr(settings, "GIT_PROVIDER", "github").lower()
        cls = _PROVIDERS.get(provider_name)
        if cls is None:
            raise ValueError(
                f"Unknown GIT_PROVIDER: {provider_name!r}. "
                f"Supported: {', '.join(_PROVIDERS.keys())}"
            )
        _cached_provider = cls()
        logger.info("Git provider: %s (%s)", provider_name, cls.__name__)
    return _cached_provider
