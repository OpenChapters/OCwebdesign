import mimetypes
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Book, BookChapter, BookPart, BuildJob

import re

def _serve_pdf(pdf_path: Path, title: str) -> FileResponse:
    """Serve a PDF file with a sanitized filename. FileResponse closes the file."""
    # Sanitize title for use as filename: keep alphanumeric, spaces, hyphens, underscores
    safe_title = re.sub(r'[^\w\s-]', '', title).strip() or "download"
    response = FileResponse(
        open(pdf_path, "rb"),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'attachment; filename="{safe_title}.pdf"'
    return response
from .serializers import (
    BookChapterSerializer,
    BookListSerializer,
    BookPartSerializer,
    BookSerializer,
    BuildJobSerializer,
)
from .tasks import build_book, build_book_html


# ── Book CRUD ─────────────────────────────────────────────────────────────────

class BookListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return BookSerializer
        return BookListSerializer

    def get_queryset(self):
        return Book.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BookDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BookSerializer

    def get_queryset(self):
        return Book.objects.filter(user=self.request.user)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


# ── Cover Image ───────────────────────────────────────────────────────────────

class CoverImageView(APIView):
    """POST /api/books/<book_pk>/cover/ — upload a cover image PDF.
    DELETE /api/books/<book_pk>/cover/ — remove the uploaded cover image."""

    permission_classes = [IsAuthenticated]

    def post(self, request, book_pk):
        book = get_object_or_404(Book, pk=book_pk, user=request.user)
        file = request.FILES.get("cover_image")
        if not file:
            return Response({"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)
        if not file.name.lower().endswith(".pdf"):
            return Response({"detail": "File must be a PDF."}, status=status.HTTP_400_BAD_REQUEST)
        if file.size > 50 * 1024 * 1024:  # 50MB limit
            return Response({"detail": "File too large (max 50MB)."}, status=status.HTTP_400_BAD_REQUEST)
        # Delete old cover if exists
        if book.cover_image:
            book.cover_image.delete(save=False)
        book.cover_image = file
        book.save(update_fields=["cover_image"])
        return Response({"detail": "Cover image uploaded.", "has_cover_image": True})

    def delete(self, request, book_pk):
        book = get_object_or_404(Book, pk=book_pk, user=request.user)
        if book.cover_image:
            book.cover_image.delete(save=False)
            book.cover_image = ""
            book.save(update_fields=["cover_image"])
        return Response({"detail": "Cover image removed.", "has_cover_image": False})


# ── Parts ─────────────────────────────────────────────────────────────────────

class PartListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _book(self, request, book_pk):
        return get_object_or_404(Book, pk=book_pk, user=request.user)

    def post(self, request, book_pk):
        book = self._book(request, book_pk)
        serializer = BookPartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(book=book)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PartDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _part(self, request, book_pk, part_pk):
        return get_object_or_404(BookPart, pk=part_pk, book__pk=book_pk, book__user=request.user)

    def patch(self, request, book_pk, part_pk):
        part = self._part(request, book_pk, part_pk)
        serializer = BookPartSerializer(part, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, book_pk, part_pk):
        part = self._part(request, book_pk, part_pk)
        part.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PartReorderView(APIView):
    """
    PATCH /api/books/<book_pk>/parts/reorder/

    Body: {"order": [<part_id>, <part_id>, ...]}
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, book_pk):
        book = get_object_or_404(Book, pk=book_pk, user=request.user)
        ids = request.data.get("order", [])
        if not isinstance(ids, list):
            return Response({"detail": "'order' must be a list."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            offset = 10000
            for part_pk in ids:
                BookPart.objects.filter(pk=part_pk, book=book).update(order=offset)
                offset += 1
            for position, part_pk in enumerate(ids):
                BookPart.objects.filter(pk=part_pk, book=book).update(order=position)
        return Response({"detail": "Parts reordered."})


# ── Chapters within a part ────────────────────────────────────────────────────

class PartChapterListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _part(self, request, book_pk, part_pk):
        return get_object_or_404(BookPart, pk=part_pk, book__pk=book_pk, book__user=request.user)

    def post(self, request, book_pk, part_pk):
        part = self._part(request, book_pk, part_pk)
        serializer = BookChapterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(part=part)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PartChapterDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _book_chapter(self, request, book_pk, part_pk, chapter_pk):
        return get_object_or_404(
            BookChapter,
            pk=chapter_pk,
            part__pk=part_pk,
            part__book__pk=book_pk,
            part__book__user=request.user,
        )

    def delete(self, request, book_pk, part_pk, chapter_pk):
        bc = self._book_chapter(request, book_pk, part_pk, chapter_pk)
        part = bc.part
        bc.delete()
        # Re-compact order values so there are no gaps
        for i, sibling in enumerate(part.book_chapters.order_by("order")):
            if sibling.order != i:
                sibling.order = i
                sibling.save(update_fields=["order"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PartChapterReorderView(APIView):
    """
    PATCH /api/books/<book_pk>/parts/<part_pk>/chapters/reorder/

    Body: {"order": [<chapter_pk>, <chapter_pk>, ...]}
    Sets order field of each BookChapter to its position in the list (0-based).
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, book_pk, part_pk):
        part = get_object_or_404(BookPart, pk=part_pk, book__pk=book_pk, book__user=request.user)
        ids = request.data.get("order", [])
        if not isinstance(ids, list):
            return Response({"detail": "'order' must be a list."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            # First shift all orders to high values to avoid unique constraint
            # violations during intermediate updates.
            offset = 10000
            for bc_pk in ids:
                BookChapter.objects.filter(pk=bc_pk, part=part).update(order=offset)
                offset += 1
            # Now set the final 0-based positions.
            for position, bc_pk in enumerate(ids):
                BookChapter.objects.filter(pk=bc_pk, part=part).update(order=position)
        return Response({"detail": "Reordered."})


# ── Build ─────────────────────────────────────────────────────────────────────

class BuildTriggerView(APIView):
    """POST /api/books/<book_pk>/build/ — enqueue a Celery build task.

    Body (JSON): {"format": "pdf" | "html" | "both"}  (default: "pdf")
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "builds"

    def post(self, request, book_pk):
        from celery import chain

        fmt = str(request.data.get("format", "pdf")).lower()
        if fmt not in ("pdf", "html", "both"):
            return Response(
                {"detail": "format must be 'pdf', 'html', or 'both'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Atomic update: only transition from draft/complete/failed to queued.
        # Prevents duplicate builds from concurrent requests.
        updated = Book.objects.filter(
            pk=book_pk,
            user=request.user,
            status__in=[Book.Status.DRAFT, Book.Status.COMPLETE, Book.Status.FAILED],
        ).update(status=Book.Status.QUEUED, last_build_format=fmt)

        if not updated:
            book = Book.objects.filter(pk=book_pk, user=request.user).first()
            if not book:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
            return Response(
                {"detail": "Build already in progress."},
                status=status.HTTP_409_CONFLICT,
            )

        if fmt == "pdf":
            build_book.delay(book_pk)
        elif fmt == "html":
            build_book_html.delay(book_pk)
        else:  # both — chain PDF then HTML so they run sequentially
            chain(build_book.si(book_pk), build_book_html.si(book_pk)).delay()

        return Response(
            {"detail": "Build queued.", "book_id": book_pk, "format": fmt},
            status=status.HTTP_202_ACCEPTED,
        )


class BuildStatusView(APIView):
    """GET /api/books/<book_pk>/build/status/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, book_pk):
        book = get_object_or_404(
            Book.objects.select_related("build_job"),
            pk=book_pk,
            user=request.user,
        )
        data = {"status": book.status}
        if hasattr(book, "build_job"):
            data["build_job"] = BuildJobSerializer(book.build_job).data
        return Response(data)


# ── Library ───────────────────────────────────────────────────────────────────

class DownloadPDFView(APIView):
    """GET /api/books/<book_pk>/download/ — serve the built PDF file."""

    permission_classes = [IsAuthenticated]

    def get(self, request, book_pk):
        book = get_object_or_404(
            Book.objects.select_related("build_job"),
            pk=book_pk,
            user=request.user,
        )
        if book.status != Book.Status.COMPLETE or not hasattr(book, "build_job"):
            return Response({"detail": "No completed build."}, status=status.HTTP_404_NOT_FOUND)

        pdf = Path(book.build_job.pdf_path)
        if not pdf.is_file():
            return Response({"detail": "PDF file not found."}, status=status.HTTP_404_NOT_FOUND)

        return _serve_pdf(pdf, book.title)


class DownloadPDFByTokenView(APIView):
    """
    GET /api/dl/<token>/ — download a PDF using a signed, time-limited token.

    Used in email delivery links. No JWT authentication required; the
    signed token proves the link was issued by the server. The token
    encodes both the book ID and the owner's user ID.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        import logging
        from .signing import verify_download_token

        logger = logging.getLogger(__name__)

        result = verify_download_token(token)
        if result is None:
            return Response(
                {"detail": "Download link is invalid or has expired."},
                status=status.HTTP_403_FORBIDDEN,
            )

        book_id, user_id = result

        book = get_object_or_404(
            Book.objects.select_related("build_job", "user"),
            pk=book_id,
        )

        # Verify user binding — token must match the book owner
        if user_id and book.user_id != user_id:
            return Response(
                {"detail": "Download link is invalid."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if book.status != Book.Status.COMPLETE or not hasattr(book, "build_job"):
            return Response({"detail": "No completed build."}, status=status.HTTP_404_NOT_FOUND)

        pdf = Path(book.build_job.pdf_path)
        if not pdf.is_file():
            return Response({"detail": "PDF file not found."}, status=status.HTTP_404_NOT_FOUND)

        # Audit trail for token downloads
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        if not ip:
            ip = request.META.get("REMOTE_ADDR", "")
        logger.info(
            "Token download: book_id=%d user_id=%d ip=%s",
            book_id, user_id or 0, ip,
        )

        return _serve_pdf(pdf, book.title)


class LibraryView(generics.ListAPIView):
    """GET /api/library/ — completed books for the authenticated user.

    Includes books that have either a PDF or HTML build available.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = BookListSerializer

    def get_queryset(self):
        from django.db.models import Q
        return (
            Book.objects.filter(user=self.request.user)
            .filter(
                Q(status=Book.Status.COMPLETE)
                | Q(html_built_at__isnull=False)
            )
        )


# ── Per-book HTML output ──────────────────────────────────────────────────────

_HTML_BOOK_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".txt": "text/plain; charset=utf-8",
}


def _book_html_dir(book: Book) -> Path | None:
    """Return the on-disk directory holding *book*'s HTML output, or None."""
    if not book.html_built_at:
        return None
    if book.html_path:
        p = Path(book.html_path)
        if p.is_dir():
            return p
    fallback = Path(settings.BUILD_HTML_OUTPUT_DIR) / f"book_{book.id}"
    return fallback if fallback.is_dir() else None


class BookHtmlView(APIView):
    """
    GET /api/books/<book_pk>/html/                — serve the book's landing HTML
    GET /api/books/<book_pk>/html/<path:filename> — serve any file from the HTML output

    Accepts either a JWT (``Authorization: Bearer …``) or a signed
    short-lived token via ``?t=<token>`` — needed because iframes
    cannot send the Authorization header. Tokens are minted by
    ``BookHtmlTokenView`` after verifying ownership.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def _cookie_name(self, book_pk: int) -> str:
        return f"ochtml_{book_pk}"

    def _authorize(self, request, book_pk):
        """Return (Book, token) if the caller owns the book via JWT, a
        query-string token, or a previously-set HTML-access cookie.
        Returns (None, None) on failure.
        """
        from .signing import verify_html_access_token

        def _verify(tok: str):
            verified = verify_html_access_token(tok)
            if verified is None:
                return None
            tok_book_id, tok_user_id = verified
            if tok_book_id != book_pk:
                return None
            return Book.objects.filter(pk=book_pk, user_id=tok_user_id).first()

        # 1. Token in the query string (iframe's initial src)
        token = request.query_params.get("t")
        if token:
            book = _verify(token)
            if book:
                return book, token

        # 2. Token stashed in a scoped cookie by a prior request
        cookie_tok = request.COOKIES.get(self._cookie_name(book_pk))
        if cookie_tok:
            book = _verify(cookie_tok)
            if book:
                return book, None  # cookie already set; no need to refresh it

        # 3. Fall back to standard JWT auth for direct API callers
        from rest_framework_simplejwt.authentication import JWTAuthentication

        auth = JWTAuthentication()
        try:
            result = auth.authenticate(request)
        except Exception:
            return None, None
        if result is None:
            return None, None
        user, _validated = result
        book = Book.objects.filter(pk=book_pk, user=user).first()
        return book, None

    def get(self, request, book_pk, filename=None):
        book, fresh_token = self._authorize(request, book_pk)
        if book is None:
            return HttpResponse(status=401)

        html_dir = _book_html_dir(book)
        if not html_dir:
            return Response({"detail": "No HTML build."}, status=status.HTTP_404_NOT_FOUND)

        if not filename:
            # For books, lwarp's index.html is the TOC landing page —
            # the right place for readers to arrive at first.
            filename = "index.html" if (html_dir / "index.html").exists() else "node-1.html"

        try:
            target = (html_dir / filename).resolve()
            if not str(target).startswith(str(html_dir.resolve())):
                return HttpResponse(status=403)
        except (ValueError, OSError):
            return HttpResponse(status=400)

        if not target.is_file():
            # Fall back to ImageFolder for bare asset names
            target = (html_dir / "ImageFolder" / filename).resolve()
            if (
                not str(target).startswith(str(html_dir.resolve()))
                or not target.is_file()
            ):
                return HttpResponse(status=404)

        suffix = target.suffix.lower()
        content_type = _HTML_BOOK_CONTENT_TYPES.get(suffix)
        if not content_type:
            content_type = (
                mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            )

        response = FileResponse(open(target, "rb"), content_type=content_type)
        response["Cache-Control"] = "private, max-age=3600"
        response["X-Frame-Options"] = "SAMEORIGIN"

        # Plant a scoped cookie so follow-up requests for iframe
        # sub-resources (CSS, SVG) — which the browser issues without
        # the ?t=<token> query string — are still authorized.
        if fresh_token:
            response.set_cookie(
                self._cookie_name(book_pk),
                fresh_token,
                max_age=4 * 3600,
                httponly=True,
                samesite="Strict",
                path=f"/api/books/{book_pk}/html/",
            )
        return response


class BookHtmlTokenView(APIView):
    """GET /api/books/<book_pk>/html-token/ — mint a short-lived HTML access token.

    The token is required for iframe <src> requests since iframes
    cannot send the Authorization header. Valid for ~4 hours.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, book_pk):
        from .signing import make_html_access_token

        book = get_object_or_404(Book, pk=book_pk, user=request.user)
        if not _book_html_dir(book):
            return Response({"detail": "No HTML build."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"token": make_html_access_token(book.id, request.user.id)})


def _serve_book_html_zip(book: Book) -> FileResponse | Response:
    """Stream a book's pre-built HTML zip archive, or return a 404 Response."""
    html_dir = _book_html_dir(book)
    if not html_dir:
        return Response({"detail": "No HTML build."}, status=status.HTTP_404_NOT_FOUND)

    zip_path = html_dir / "book.zip"
    if not zip_path.is_file():
        return Response(
            {"detail": "HTML archive not available."},
            status=status.HTTP_404_NOT_FOUND,
        )

    import re as _re
    safe_title = _re.sub(r"[^\w\s-]", "", book.title).strip() or "book"
    response = FileResponse(open(zip_path, "rb"), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{safe_title}.zip"'
    return response


class DownloadBookHtmlView(APIView):
    """GET /api/books/<book_pk>/download-html/ — download the HTML zip (JWT auth)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, book_pk):
        book = get_object_or_404(Book, pk=book_pk, user=request.user)
        return _serve_book_html_zip(book)


class DownloadBookHtmlByTokenView(APIView):
    """
    GET /api/dl-html/<token>/ — download the HTML zip using a signed,
    time-limited token from an email delivery link. No JWT required;
    the signed token proves the link was issued by the server and
    encodes both the book ID and the owner's user ID.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        import logging
        from .signing import verify_download_token

        logger = logging.getLogger(__name__)

        result = verify_download_token(token)
        if result is None:
            return Response(
                {"detail": "Download link is invalid or has expired."},
                status=status.HTTP_403_FORBIDDEN,
            )

        book_id, user_id = result
        book = get_object_or_404(Book.objects.select_related("user"), pk=book_id)

        if user_id and book.user_id != user_id:
            return Response(
                {"detail": "Download link is invalid."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Audit trail for token downloads
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        if not ip:
            ip = request.META.get("REMOTE_ADDR", "")
        logger.info(
            "Token HTML download: book_id=%d user_id=%d ip=%s",
            book_id, user_id or 0, ip,
        )

        return _serve_book_html_zip(book)
