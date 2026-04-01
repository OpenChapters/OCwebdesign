import logging
import tempfile
from pathlib import Path

import httpx
from django.conf import settings
from django.http import FileResponse, HttpResponse
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from .models import Chapter, Discipline
from .serializers import ChapterSerializer, DisciplineSerializer

logger = logging.getLogger(__name__)

# Local cache directory for cover images
COVER_CACHE_DIR = Path(settings.BASE_DIR) / "media" / "covers"


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
