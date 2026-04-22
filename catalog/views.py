import logging
import mimetypes
import tempfile
from pathlib import Path

import httpx
from django.conf import settings
from django.http import FileResponse, HttpResponse
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Chapter, ChapterSearchIndex, Discipline
from .serializers import ChapterSerializer, DisciplineSerializer

logger = logging.getLogger(__name__)

# Local cache directory for cover images
COVER_CACHE_DIR = Path(settings.BASE_DIR) / "media" / "covers"

# Directory where per-chapter HTML output is stored
HTML_DIR = Path(settings.BASE_DIR) / "media" / "html"


class DisciplineListView(generics.ListAPIView):
    """GET /api/disciplines/ — list all published disciplines."""
    queryset = Discipline.objects.filter(published=True)
    serializer_class = DisciplineSerializer
    permission_classes = [AllowAny]
    pagination_class = None  # No pagination; small list


class ChapterListView(generics.ListAPIView):
    serializer_class = ChapterSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Chapter.objects.filter(published=True).select_related("discipline")
        discipline = self.request.query_params.get("discipline", "").strip()
        if discipline:
            qs = qs.filter(discipline__slug=discipline)
        return qs


class ChapterDetailView(generics.RetrieveAPIView):
    queryset = Chapter.objects.filter(published=True)
    serializer_class = ChapterSerializer
    permission_classes = [AllowAny]


class ChapterCoverView(APIView):
    """
    GET /api/chapters/<id>/cover/ — serve the chapter's cover image.

    Proxies the image from GitHub on first request and caches it locally.
    Subsequent requests are served from the local cache. Uses atomic
    write-to-temp-then-rename to prevent race conditions.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        try:
            chapter = Chapter.objects.get(pk=pk, published=True)
        except Chapter.DoesNotExist:
            return HttpResponse(status=404)

        if not chapter.cover_image_url:
            return HttpResponse(status=404)

        # Check local cache
        COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = COVER_CACHE_DIR / f"{chapter.id}.png"

        if not cache_file.exists():
            # Fetch from GitHub and cache atomically (write to temp, then rename)
            try:
                resp = httpx.get(chapter.cover_image_url, timeout=15, follow_redirects=True)
                if resp.status_code != 200:
                    logger.warning("Cover fetch failed for chapter %d: HTTP %d", pk, resp.status_code)
                    return HttpResponse(status=502)
                # Atomic write: temp file in same directory, then rename
                fd, tmp_path = tempfile.mkstemp(dir=str(COVER_CACHE_DIR), suffix=".tmp")
                try:
                    with open(fd, "wb") as f:
                        f.write(resp.content)
                    Path(tmp_path).rename(cache_file)
                except Exception:
                    Path(tmp_path).unlink(missing_ok=True)
                    raise
            except httpx.HTTPError as e:
                logger.warning("Cover fetch error for chapter %d: %s", pk, e)
                return HttpResponse(status=502)
            except Exception:
                logger.exception("Unexpected error caching cover for chapter %d", pk)
                return HttpResponse(status=502)

        # ETag based on file modification time for conditional requests
        import hashlib
        mtime = str(cache_file.stat().st_mtime)
        etag = hashlib.md5(f"{chapter.id}:{mtime}".encode()).hexdigest()

        if_none_match = request.META.get("HTTP_IF_NONE_MATCH", "")
        if if_none_match == f'"{etag}"':
            return HttpResponse(status=304)

        response = FileResponse(
            open(cache_file, "rb"),
            content_type="image/png",
        )
        response["Cache-Control"] = "public, max-age=86400"
        response["ETag"] = f'"{etag}"'
        return response


class ChapterHtmlView(APIView):
    """
    GET /api/chapters/<id>/html/              — serve index.html
    GET /api/chapters/<id>/html/<filename>    — serve any file from the HTML output

    Serves pre-built lwarp HTML output for a chapter. Returns 404 if
    HTML has not been built for the chapter.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    _CONTENT_TYPES = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".txt": "text/plain; charset=utf-8",
    }

    def get(self, request, pk, filename=None):
        try:
            chapter = Chapter.objects.get(pk=pk, published=True)
        except Chapter.DoesNotExist:
            return HttpResponse(status=404)

        if not chapter.chabbr or not chapter.html_built_at:
            return HttpResponse(status=404)

        chapter_dir = HTML_DIR / chapter.chabbr
        if not chapter_dir.is_dir():
            return HttpResponse(status=404)

        # Default to node-1.html (chapter content) rather than index.html
        # (which is lwarp's landing page with only MathJax macro definitions)
        if not filename:
            if (chapter_dir / "node-1.html").exists():
                filename = "node-1.html"
            else:
                filename = "index.html"

        # Prevent path traversal
        try:
            target = (chapter_dir / filename).resolve()
            if not str(target).startswith(str(chapter_dir.resolve())):
                return HttpResponse(status=403)
        except (ValueError, OSError):
            return HttpResponse(status=400)

        if not target.is_file():
            # Check ImageFolder subdirectory
            target = (chapter_dir / "ImageFolder" / filename).resolve()
            if not str(target).startswith(str(chapter_dir.resolve())) or not target.is_file():
                return HttpResponse(status=404)

        suffix = target.suffix.lower()
        content_type = self._CONTENT_TYPES.get(suffix)
        if not content_type:
            content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"

        response = FileResponse(open(target, "rb"), content_type=content_type)
        response["Cache-Control"] = "public, max-age=3600"
        response["X-Frame-Options"] = "SAMEORIGIN"
        return response


class ChapterSearchView(APIView):
    """GET /api/chapters/search/?q=<query>&limit=20 — full-text search over
    all published chapters with built HTML.

    Returns a ranked list of matching sections with highlighted snippets
    and deep-link URLs into the HTML reader.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank

        query_text = request.query_params.get("q", "").strip()
        if not query_text or len(query_text) < 2:
            return Response({"results": []})

        try:
            limit = max(1, min(int(request.query_params.get("limit", 20)), 100))
        except (ValueError, TypeError):
            limit = 20

        # Use websearch syntax so users can type "rotation matrix" or "quaternion OR euler"
        query = SearchQuery(query_text, config="english", search_type="websearch")

        qs = (
            ChapterSearchIndex.objects
            .filter(chapter__published=True, search_vector=query)
            .select_related("chapter", "chapter__discipline")
            .annotate(
                rank=SearchRank("search_vector", query),
                headline=SearchHeadline(
                    "text_content",
                    query,
                    config="english",
                    max_words=30,
                    min_words=10,
                    short_word=3,
                    highlight_all=False,
                    start_sel="<mark>",
                    stop_sel="</mark>",
                ),
            )
            .order_by("-rank")[:limit]
        )

        results = []
        for e in qs:
            anchor_frag = f"#{e.anchor}" if e.anchor else ""
            results.append({
                "chapter_id": e.chapter.id,
                "chapter_title": e.chapter.title,
                "chabbr": e.chapter.chabbr,
                "discipline": (
                    {
                        "name": e.chapter.discipline.name,
                        "color_primary": e.chapter.discipline.color_primary,
                    } if e.chapter.discipline else None
                ),
                "section_title": e.section_title,
                "snippet": e.headline,
                "read_url": f"/chapters/{e.chapter.id}/read?node={e.html_node}{anchor_frag}",
            })

        return Response({"results": results, "count": len(results)})
