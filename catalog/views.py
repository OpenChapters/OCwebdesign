import csv
import logging
import mimetypes
import re
import tempfile
from pathlib import Path

import httpx
from django.conf import settings
from django.db.models import Q
from django.http import FileResponse, HttpResponse
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Chapter, ChapterSearchIndex, Discipline, Example
from .serializers import (
    ChapterSerializer,
    DisciplineSerializer,
    ExampleDetailSerializer,
    ExampleListSerializer,
    ExampleWriteSerializer,
)

logger = logging.getLogger(__name__)

# Local cache directory for cover images
COVER_CACHE_DIR = Path(settings.BASE_DIR) / "media" / "covers"

# Directory where per-chapter HTML output is stored
HTML_DIR = Path(settings.BASE_DIR) / "media" / "html"

# Directory where per-chapter labels-PDF artifacts live (foundational only)
PDF_LABELS_DIR = Path(settings.BASE_DIR) / "media" / "pdf_labels"


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


class ChapterCatalogCsvView(APIView):
    """GET /api/chapters/catalog.csv — public CSV of all published chapters.

    Used by the public Catalog page so prospective authors can pull a
    complete inventory of what's already in the collection without
    creating an account.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        chapters = (
            Chapter.objects
            .filter(published=True)
            .select_related("discipline")
            .order_by("discipline__order", "discipline__name", "title")
        )

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            'attachment; filename="openchapters-catalog.csv"'
        )
        # UTF-8 BOM so Excel opens accented characters correctly
        response.write("﻿")
        writer = csv.writer(response)
        writer.writerow([
            "chabbr",
            "title",
            "discipline",
            "type",
            "authors",
            "last_updated",
            "html_built",
            "url",
        ])
        for c in chapters:
            writer.writerow([
                c.chabbr or "",
                c.title,
                c.discipline.name if c.discipline else "",
                c.chapter_type,
                "; ".join(c.authors) if c.authors else "",
                c.last_updated.date().isoformat() if c.last_updated else "",
                c.html_built_at.date().isoformat() if c.html_built_at else "",
                request.build_absolute_uri(f"/chapters/{c.id}"),
            ])
        return response


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


class ChapterPdfLabelsView(APIView):
    """GET /api/chapters/<id>/pdf-labels/ — labels-PDF for foundational chapters.

    Serves the per-chapter PDF typeset with showkeys enabled, so
    prospective authors can see the existing label scheme. 404 when
    the chapter is not foundational or the artifact has not been built.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        try:
            chapter = Chapter.objects.get(pk=pk, published=True)
        except Chapter.DoesNotExist:
            return HttpResponse(status=404)

        if (
            chapter.chapter_type != Chapter.ChapterType.FOUNDATIONAL
            or not chapter.chabbr
        ):
            return HttpResponse(status=404)

        pdf_path = PDF_LABELS_DIR / f"{chapter.chabbr}.pdf"
        if not pdf_path.is_file():
            return HttpResponse(status=404)

        response = FileResponse(open(pdf_path, "rb"), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{chapter.chabbr}-labels.pdf"'
        )
        response["Cache-Control"] = "public, max-age=3600"
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

        # Default to prefix matching ("sym" -> "sym:*") so users get hits as
        # they type — Postgres' English stemmer doesn't match prefixes on its
        # own, so a bare "sym" never finds "symbol" or "symmetry". Fall back
        # to websearch syntax when the query uses quoted phrases, OR, or "-"
        # exclusion, since the raw-prefix form can't express those.
        if re.search(r'"|\bOR\b|(?:^|\s)-\w', query_text, re.IGNORECASE):
            query = SearchQuery(query_text, config="english", search_type="websearch")
        else:
            tokens = [t for t in re.split(r"[^\w]+", query_text) if t]
            if tokens:
                raw = " & ".join(f"{t}:*" for t in tokens)
                query = SearchQuery(raw, config="english", search_type="raw")
            else:
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


# ── Examples (worked-examples library, todo #5 phase 1) ──────────────────────

def _example_base_qs():
    return (
        Example.objects
        .select_related("primary_chapter", "author")
        .prefetch_related("chapters")
    )


class ExamplePublicListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/examples/ — list PUBLISHED examples (AllowAny).
    POST /api/examples/ — create as DRAFT (IsAuthenticated).

    List filters: ?chapter=<chabbr> (matches any tagged chapter, not
    just primary), ?difficulty=, ?search= (icontains on text fields).
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ExampleWriteSerializer
        return ExampleListSerializer

    def get_queryset(self):
        qs = _example_base_qs().filter(status=Example.Status.PUBLISHED)
        chabbr = self.request.query_params.get("chapter", "").strip()
        if chabbr:
            qs = qs.filter(chapters__chabbr=chabbr).distinct()
        difficulty = self.request.query_params.get("difficulty", "").strip()
        if difficulty in Example.Difficulty.values:
            qs = qs.filter(difficulty=difficulty)
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(statement_tex__icontains=search)
                | Q(solution_tex__icontains=search)
            )
        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, status=Example.Status.DRAFT)

    def create(self, request, *args, **kwargs):
        # Override to return the detail serializer's payload after create
        # rather than the write serializer's flat representation.
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        self.perform_create(ser)
        return Response(
            ExampleDetailSerializer(ser.instance).data,
            status=status.HTTP_201_CREATED,
        )


class ExamplePublicDetailView(generics.RetrieveAPIView):
    """GET /api/examples/<id>/ — published example detail."""
    serializer_class = ExampleDetailSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return _example_base_qs().filter(status=Example.Status.PUBLISHED)


class ExampleMineView(generics.ListAPIView):
    """GET /api/examples/mine/ — author's own examples across all statuses."""
    serializer_class = ExampleListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _example_base_qs().filter(author=self.request.user)


class ExampleAuthorManageView(APIView):
    """
    GET    /api/examples/<id>/manage/ — view own example (any status).
    PATCH  /api/examples/<id>/manage/ — update own DRAFT or REJECTED.
    DELETE /api/examples/<id>/manage/ — delete own DRAFT.

    Editing a REJECTED example moves it back to DRAFT so the author
    can iterate before re-submitting.
    """
    permission_classes = [IsAuthenticated]

    def _get_own(self, pk):
        try:
            return _example_base_qs().get(pk=pk, author=self.request.user)
        except Example.DoesNotExist:
            return None

    def get(self, request, pk):
        ex = self._get_own(pk)
        if ex is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ExampleDetailSerializer(ex).data)

    def patch(self, request, pk):
        ex = self._get_own(pk)
        if ex is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if ex.status not in (Example.Status.DRAFT, Example.Status.REJECTED):
            return Response(
                {"detail": "Only drafts and rejected examples can be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = ExampleWriteSerializer(ex, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        # Editing a rejected example moves it back to DRAFT so the author
        # can iterate and re-submit.
        save_kwargs = {}
        if ex.status == Example.Status.REJECTED:
            save_kwargs["status"] = Example.Status.DRAFT
            save_kwargs["rejection_reason"] = ""
        ex = ser.save(**save_kwargs)
        return Response(ExampleDetailSerializer(ex).data)

    def delete(self, request, pk):
        ex = self._get_own(pk)
        if ex is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if ex.status != Example.Status.DRAFT:
            return Response(
                {"detail": "Only drafts can be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ex.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExampleSubmitView(APIView):
    """POST /api/examples/<id>/submit/ — DRAFT or REJECTED → PENDING.

    Phase 1: no preview-freshness gate yet (snippet compile lands in
    Phase 2). For now any author can submit.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            ex = Example.objects.get(pk=pk, author=request.user)
        except Example.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if ex.status not in (Example.Status.DRAFT, Example.Status.REJECTED):
            return Response(
                {"detail": "Only drafts and rejected examples can be submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ex.status = Example.Status.PENDING
        ex.rejection_reason = ""
        ex.save(update_fields=["status", "rejection_reason", "updated_at"])
        return Response(ExampleDetailSerializer(ex).data)


class ExampleAdminQueueView(generics.ListAPIView):
    """GET /api/admin/examples/?status=pending — review queue."""
    serializer_class = ExampleDetailSerializer
    permission_classes = [IsAdminUser]
    pagination_class = None

    def get_queryset(self):
        qs = _example_base_qs()
        st = self.request.query_params.get("status", Example.Status.PENDING).strip()
        if st in Example.Status.values:
            qs = qs.filter(status=st)
        return qs


class ExampleAdminApproveView(APIView):
    """POST /api/admin/examples/<id>/approve/ — PENDING → PUBLISHED."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            ex = Example.objects.get(pk=pk)
        except Example.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if ex.status != Example.Status.PENDING:
            return Response(
                {"detail": "Only pending examples can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ex.status = Example.Status.PUBLISHED
        ex.rejection_reason = ""
        ex.save(update_fields=["status", "rejection_reason", "updated_at"])
        return Response(ExampleDetailSerializer(ex).data)


class ExampleAdminRejectView(APIView):
    """POST /api/admin/examples/<id>/reject/ — PENDING → REJECTED with reason."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            ex = Example.objects.get(pk=pk)
        except Example.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if ex.status != Example.Status.PENDING:
            return Response(
                {"detail": "Only pending examples can be rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reason = (request.data.get("rejection_reason") or "").strip()
        if not reason:
            return Response(
                {"rejection_reason": "A rejection reason is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ex.status = Example.Status.REJECTED
        ex.rejection_reason = reason
        ex.save(update_fields=["status", "rejection_reason", "updated_at"])
        return Response(ExampleDetailSerializer(ex).data)
