import csv
import logging
import mimetypes
import re
import tempfile
from pathlib import Path

import httpx
from django.conf import settings
from django.core.signing import BadSignature, TimestampSigner
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Chapter, ChapterSearchIndex, Discipline, Example, ExampleFigure, ExampleVersion
from .serializers import (
    ChapterSerializer,
    DisciplineSerializer,
    ExampleDetailSerializer,
    ExampleFigureSerializer,
    ExampleListSerializer,
    ExampleVersionSerializer,
    ExampleWriteSerializer,
)

logger = logging.getLogger(__name__)

# Local cache directory for cover images
COVER_CACHE_DIR = Path(settings.BASE_DIR) / "media" / "covers"

# Directory where per-chapter HTML output is stored
HTML_DIR = Path(settings.BASE_DIR) / "media" / "html"

# Directory where per-chapter labels-PDF artifacts live (foundational only)
PDF_LABELS_DIR = Path(settings.BASE_DIR) / "media" / "pdf_labels"

# Directory where worked-example snippet preview PDFs live
EXAMPLES_DIR = Path(settings.BASE_DIR) / "media" / "examples"

# Signed-URL helper for the preview PDF. The iframe in the example editor
# is a plain browser GET that can't carry the JWT, so for non-PUBLISHED
# examples we mint a short-lived signed token that the URL itself
# carries. PUBLISHED examples are already anonymous-readable; signing is
# only needed to read drafts/pending/rejected.
_EXAMPLE_PREVIEW_SIGNER = TimestampSigner(salt="catalog.example-preview")
EXAMPLE_PREVIEW_TOKEN_TTL = 30 * 60  # 30 minutes


def make_example_preview_token(example_id: int) -> str:
    return _EXAMPLE_PREVIEW_SIGNER.sign(str(example_id))


def verify_example_preview_token(token: str, example_id: int) -> bool:
    try:
        unsigned = _EXAMPLE_PREVIEW_SIGNER.unsign(
            token, max_age=EXAMPLE_PREVIEW_TOKEN_TTL,
        )
    except (BadSignature, ValueError):
        return False
    try:
        return int(unsigned) == int(example_id)
    except ValueError:
        return False


class DisciplineListView(generics.ListAPIView):
    """GET /api/disciplines/ — list all published disciplines."""
    queryset = Discipline.objects.filter(published=True)
    serializer_class = DisciplineSerializer
    permission_classes = [AllowAny]
    pagination_class = None  # No pagination; small list


def _annotate_examples_count(qs):
    """Annotate a Chapter queryset with examples_count_annotated.

    The serializer reads this attribute directly to avoid the per-row
    COUNT query on list views.
    """
    return qs.annotate(
        examples_count_annotated=Count(
            "examples",
            filter=Q(examples__status="published"),
            distinct=True,
        )
    )


class ChapterListView(generics.ListAPIView):
    serializer_class = ChapterSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = (
            Chapter.objects.filter(published=True)
            .select_related("discipline")
        )
        qs = _annotate_examples_count(qs)
        discipline = self.request.query_params.get("discipline", "").strip()
        if discipline:
            qs = qs.filter(discipline__slug=discipline)
        return qs


class ChapterDetailView(generics.RetrieveAPIView):
    serializer_class = ChapterSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return _annotate_examples_count(
            Chapter.objects.filter(published=True)
        )


@extend_schema(exclude=True)
class ChapterCatalogCsvView(APIView):
    """GET /api/chapters/catalog.csv — public CSV of all published chapters.

    Used by the public Catalog page so prospective authors can pull a
    complete inventory of what's already in the collection without
    creating an account.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        chapters = _annotate_examples_count(
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
            "examples",
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
                c.examples_count_annotated,
                request.build_absolute_uri(f"/chapters/{c.id}"),
            ])
        return response


@extend_schema(exclude=True)
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


@extend_schema(exclude=True)
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


@extend_schema(exclude=True)
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
        .prefetch_related("chapters", "figures")
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
        from .signals import set_current_user

        ex = self._get_own(pk)
        if ex is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if ex.status not in (
            Example.Status.DRAFT,
            Example.Status.REJECTED,
            Example.Status.PUBLISHED,
        ):
            return Response(
                {"detail": "This example cannot be edited in its current state."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = ExampleWriteSerializer(ex, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        # Status transitions on edit:
        #   REJECTED → DRAFT     so the author can iterate and re-submit
        #   PUBLISHED → PENDING  so an admin re-reviews before the change
        #                        becomes public; preview state is cleared
        #                        so the queue page shows it as stale.
        save_kwargs = {}
        if ex.status == Example.Status.REJECTED:
            save_kwargs["status"] = Example.Status.DRAFT
            save_kwargs["rejection_reason"] = ""
        elif ex.status == Example.Status.PUBLISHED:
            save_kwargs["status"] = Example.Status.PENDING
            save_kwargs["preview_built_at"] = None
            save_kwargs["preview_build_log"] = ""
        set_current_user(request.user)
        try:
            ex = ser.save(**save_kwargs)
        finally:
            set_current_user(None)
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


class ExampleVersionListView(generics.ListAPIView):
    """GET /api/examples/<id>/versions/

    Returns the prior-state ledger for *id* in newest-first order so
    the most recent revision is at the top. Access is restricted to
    the example's author and staff — versions can contain pre-
    rejection content the author later removed, and that history
    shouldn't be public.

    Returns 404 for both "example does not exist" and "you can't see
    this one" so the endpoint doesn't leak which examples have a
    history.
    """

    serializer_class = ExampleVersionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        pk = self.kwargs["pk"]
        try:
            ex = Example.objects.get(pk=pk)
        except Example.DoesNotExist:
            return ExampleVersion.objects.none()
        user = self.request.user
        if ex.author_id != user.id and not user.is_staff:
            return ExampleVersion.objects.none()
        return (
            ExampleVersion.objects
            .filter(example_id=pk)
            .select_related("created_by")
            .order_by("-version_no")
        )

    def list(self, request, *args, **kwargs):
        pk = self.kwargs["pk"]
        try:
            ex = Example.objects.get(pk=pk)
        except Example.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if ex.author_id != request.user.id and not request.user.is_staff:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return super().list(request, *args, **kwargs)


class ExampleSubmitView(APIView):
    """POST /api/examples/<id>/submit/ — DRAFT or REJECTED → PENDING.

    Requires a fresh preview compile: preview_built_at must be set and
    no older than the example's last edit. Authors are responsible for
    clicking "Preview" again after every edit (no auto-rebuild).
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
        if ex.preview_built_at is None:
            return Response(
                {"detail": "Click Preview and wait for a successful compile before submitting."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if ex.preview_built_at < ex.updated_at:
            return Response(
                {"detail": "Preview is stale. Click Preview again before submitting."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ex.status = Example.Status.PENDING
        ex.rejection_reason = ""
        # Omit updated_at — auto_now=True only fires when listed in
        # update_fields. Keeping it out preserves "updated_at = last edit"
        # semantics so the preview-freshness check doesn't go stale on a
        # mere status transition.
        ex.save(update_fields=["status", "rejection_reason"])
        return Response(ExampleDetailSerializer(ex).data)


class ExamplePreviewTriggerView(APIView):
    """POST /api/examples/<id>/preview/ — enqueue a snippet preview build.

    Available to the example's author for any status; admins can also
    trigger preview rebuilds (e.g., to re-verify a published example
    against an updated preamble). Returns the Celery task ID.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            ex = Example.objects.get(pk=pk)
        except Example.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if ex.author_id != request.user.id and not request.user.is_staff:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        from catalog.tasks import build_example_preview_task
        task = build_example_preview_task.delay(ex.id)
        return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)


@extend_schema(exclude=True)
class ExampleFigureFileView(APIView):
    """GET /api/examples/<id>/figures/<figure_id>/file
    Serves the figure file. PUBLISHED examples are anonymous-readable;
    everything else requires the example's author or staff.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk, figure_id):
        try:
            ex = Example.objects.get(pk=pk)
        except Example.DoesNotExist:
            return HttpResponse(status=404)
        if ex.status != Example.Status.PUBLISHED:
            user = request.user if request.user.is_authenticated else None
            if user is None or (user.id != ex.author_id and not user.is_staff):
                return HttpResponse(status=404)
        try:
            figure = ex.figures.get(pk=figure_id)
        except ExampleFigure.DoesNotExist:
            return HttpResponse(status=404)
        try:
            fh = figure.file.open("rb")
        except FileNotFoundError:
            return HttpResponse(status=404)
        content_type = mimetypes.guess_type(figure.original_filename)[0] or "application/octet-stream"
        response = FileResponse(fh, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{figure.original_filename}"'
        response["Cache-Control"] = "private, max-age=300"
        return response


class ExampleFigureUploadView(APIView):
    """POST /api/examples/<id>/figures/ — upload a figure (multipart).

    Only the example's author or staff can upload, and only when the
    example is in DRAFT or REJECTED state. Validates extension and size.
    The original filename is what \\includegraphics{...} must match in
    the LaTeX source — the on-disk path is namespaced under the example
    id so collisions across examples don't matter.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            ex = Example.objects.get(pk=pk)
        except Example.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if ex.author_id != request.user.id and not request.user.is_staff:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if ex.status not in (Example.Status.DRAFT, Example.Status.REJECTED):
            return Response(
                {"detail": "Figures can only be added to drafts and rejected examples."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"file": "A file upload is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        original = upload.name or ""
        ext = Path(original).suffix.lower()
        if ext not in ExampleFigure.ALLOWED_EXTENSIONS:
            allowed = ", ".join(ExampleFigure.ALLOWED_EXTENSIONS)
            return Response(
                {"file": f"Unsupported extension {ext!r}. Allowed: {allowed}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if upload.size > ExampleFigure.MAX_BYTES:
            cap_mb = ExampleFigure.MAX_BYTES // (1024 * 1024)
            return Response(
                {"file": f"File exceeds the {cap_mb} MB cap."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reject duplicate filenames within the same example — \includegraphics
        # references the basename, so two figures with the same name would
        # collide at build time.
        if ex.figures.filter(original_filename=original).exists():
            return Response(
                {"file": "A figure with this filename is already attached."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        caption = (request.data.get("caption") or "").strip()
        figure = ExampleFigure.objects.create(
            example=ex,
            file=upload,
            original_filename=original,
            caption=caption,
            order=ex.figures.count(),
        )
        # Adding figures invalidates any prior preview compile.
        ex.preview_built_at = None
        ex.save(update_fields=["preview_built_at"])
        return Response(
            ExampleFigureSerializer(figure).data,
            status=status.HTTP_201_CREATED,
        )


class ExampleFigureDeleteView(APIView):
    """DELETE /api/examples/<id>/figures/<figure_id>/ — remove a figure."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, figure_id):
        try:
            ex = Example.objects.get(pk=pk)
        except Example.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if ex.author_id != request.user.id and not request.user.is_staff:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if ex.status not in (Example.Status.DRAFT, Example.Status.REJECTED):
            return Response(
                {"detail": "Figures can only be removed from drafts and rejected examples."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            figure = ex.figures.get(pk=figure_id)
        except ExampleFigure.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        # Best-effort file removal; the row drives the LaTeX build.
        try:
            figure.file.delete(save=False)
        except Exception:
            logger.warning("Failed to delete figure file for figure %s", figure.pk, exc_info=True)
        figure.delete()
        ex.preview_built_at = None
        ex.save(update_fields=["preview_built_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(exclude=True)
class ExamplePreviewPdfView(APIView):
    """GET /api/examples/<id>/preview.pdf[?t=<signed-token>]

    Serves the cached preview PDF. Authorization rules, in order:
    - PUBLISHED examples: open to anyone.
    - A valid signed `t` token: open (used by the editor's iframe and
      "Open in new tab" links, which can't attach the JWT).
    - Author or staff via JWT: open.
    - Otherwise: 404.

    Tokens are minted by ExampleDetailSerializer.preview_pdf_url so the
    frontend uses the URL straight from the API response.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        try:
            ex = Example.objects.get(pk=pk)
        except Example.DoesNotExist:
            return HttpResponse(status=404)

        if ex.status != Example.Status.PUBLISHED:
            authorized = False
            token = request.query_params.get("t", "")
            if token and verify_example_preview_token(token, ex.id):
                authorized = True
            else:
                user = request.user if request.user.is_authenticated else None
                if user is not None and (user.id == ex.author_id or user.is_staff):
                    authorized = True
            if not authorized:
                return HttpResponse(status=404)

        pdf_path = EXAMPLES_DIR / f"{ex.id}.pdf"
        if not pdf_path.is_file():
            return HttpResponse(status=404)

        response = FileResponse(open(pdf_path, "rb"), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="example-{ex.id}.pdf"'
        response["Cache-Control"] = "private, max-age=60"
        # Django's default XFrameOptionsMiddleware adds DENY, which would
        # block the editor's iframe from rendering the PDF. Override.
        response["X-Frame-Options"] = "SAMEORIGIN"
        return response


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
        # Omit updated_at — auto_now=True only fires when listed in
        # update_fields. Keeping it out preserves "updated_at = last edit"
        # semantics so the preview-freshness check doesn't go stale on a
        # mere status transition.
        ex.save(update_fields=["status", "rejection_reason"])
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
        # Omit updated_at — auto_now=True only fires when listed in
        # update_fields. Keeping it out preserves "updated_at = last edit"
        # semantics so the preview-freshness check doesn't go stale on a
        # mere status transition.
        ex.save(update_fields=["status", "rejection_reason"])
        return Response(ExampleDetailSerializer(ex).data)


class ExampleAdminImportDryRunView(APIView):
    """POST /api/admin/examples/import/dry-run/ — parse and validate a
    batch zip without writing to the DB. Returns the per-entry report.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        from catalog.services.example_import import parse_zip, report_to_dict

        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"file": "A zip file upload is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        zip_bytes = upload.read()
        report = parse_zip(zip_bytes=zip_bytes, default_author=request.user)
        return Response(report_to_dict(report))


class ExampleAdminImportCommitView(APIView):
    """POST /api/admin/examples/import/commit/ — re-validate then persist.

    `default_status` form field controls the status assigned to newly
    created examples (existing ones keep their current status). For
    admin imports the choices are PENDING (sent to the review queue) or
    PUBLISHED (live immediately).
    """
    permission_classes = [IsAdminUser]

    ALLOWED_DEFAULT_STATUSES = (Example.Status.PENDING, Example.Status.PUBLISHED)

    def post(self, request):
        from catalog.services.example_import import (
            commit_report,
            parse_zip,
            report_to_dict,
        )

        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"file": "A zip file upload is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        default_status = (request.data.get("default_status") or Example.Status.PENDING).strip()
        if default_status not in self.ALLOWED_DEFAULT_STATUSES:
            return Response(
                {"default_status": (
                    f"Must be one of: {', '.join(self.ALLOWED_DEFAULT_STATUSES)}."
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        zip_bytes = upload.read()
        report = parse_zip(zip_bytes=zip_bytes, default_author=request.user)
        if report.has_errors:
            return Response(report_to_dict(report), status=status.HTTP_400_BAD_REQUEST)

        report = commit_report(
            report=report,
            default_author=request.user,
            default_status=default_status,
        )
        # commit_report can append global_errors (e.g. invalid status) —
        # surface those as a 400 even though parse succeeded.
        if report.has_errors:
            return Response(report_to_dict(report), status=status.HTTP_400_BAD_REQUEST)
        return Response(report_to_dict(report), status=status.HTTP_201_CREATED)


def _author_import_enabled() -> bool:
    """Read the author-batch-import flag without crashing if admin_api
    isn't installed yet (e.g. during migrations)."""
    try:
        from admin_api.models import SiteSetting
        return bool(SiteSetting.get("author_batch_import_enabled"))
    except Exception:  # pragma: no cover — defensive
        return False


class ExampleAuthorImportDryRunView(APIView):
    """POST /api/examples/import/dry-run/ — author-side dry-run.

    Authenticated authors can validate a batch zip when the admin has
    enabled the feature in Site Settings. The parser is shared with the
    admin path; the requesting user is recorded as the author for both
    the slug-match lookup and the eventual create.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _author_import_enabled():
            return Response(
                {"detail": "Author batch-import is currently disabled."},
                status=status.HTTP_403_FORBIDDEN,
            )
        from catalog.services.example_import import parse_zip, report_to_dict

        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"file": "A zip file upload is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        zip_bytes = upload.read()
        report = parse_zip(zip_bytes=zip_bytes, default_author=request.user)
        return Response(report_to_dict(report))


class ExampleAuthorImportCommitView(APIView):
    """POST /api/examples/import/commit/ — author-side commit.

    Newly created rows are persisted as DRAFT or PENDING (admin review
    queue). Authors cannot self-publish via batch import; only admins
    can do that through the admin import endpoint.
    """
    permission_classes = [IsAuthenticated]

    ALLOWED_DEFAULT_STATUSES = (Example.Status.DRAFT, Example.Status.PENDING)

    def post(self, request):
        if not _author_import_enabled():
            return Response(
                {"detail": "Author batch-import is currently disabled."},
                status=status.HTTP_403_FORBIDDEN,
            )
        from catalog.services.example_import import (
            commit_report,
            parse_zip,
            report_to_dict,
        )

        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"file": "A zip file upload is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        default_status = (request.data.get("default_status") or Example.Status.DRAFT).strip()
        if default_status not in self.ALLOWED_DEFAULT_STATUSES:
            return Response(
                {"default_status": (
                    f"Must be one of: {', '.join(self.ALLOWED_DEFAULT_STATUSES)}."
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        zip_bytes = upload.read()
        report = parse_zip(zip_bytes=zip_bytes, default_author=request.user)
        if report.has_errors:
            return Response(report_to_dict(report), status=status.HTTP_400_BAD_REQUEST)

        report = commit_report(
            report=report,
            default_author=request.user,
            default_status=default_status,
        )
        if report.has_errors:
            return Response(report_to_dict(report), status=status.HTTP_400_BAD_REQUEST)
        return Response(report_to_dict(report), status=status.HTTP_201_CREATED)


class ExampleAdminDeleteView(APIView):
    """DELETE /api/admin/examples/<id>/ — remove an example in any state.

    Cascades to figures (ExampleFigure.example has on_delete=CASCADE) and
    cleans up the snippet preview PDF on disk. Existing book builds are
    unaffected because example content is embedded at build time.
    """
    permission_classes = [IsAdminUser]

    def delete(self, request, pk):
        try:
            ex = Example.objects.get(pk=pk)
        except Example.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        # Best-effort removal of figure files; the row delete cascades
        # via FK but FieldFile cleanup is not automatic.
        for fig in ex.figures.all():
            try:
                fig.file.delete(save=False)
            except Exception:
                logger.warning("Failed to delete figure file for figure %s", fig.pk, exc_info=True)
        pdf_path = EXAMPLES_DIR / f"{ex.id}.pdf"
        try:
            pdf_path.unlink(missing_ok=True)
        except Exception:
            logger.warning("Failed to delete preview PDF for example %s", ex.pk, exc_info=True)
        ex.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
