from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Book, BookChapter, BookPart, BuildJob
from .serializers import (
    BookChapterSerializer,
    BookListSerializer,
    BookPartSerializer,
    BookSerializer,
    BuildJobSerializer,
)
from .tasks import build_book


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
        bc.delete()
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
        for position, bc_pk in enumerate(ids):
            BookChapter.objects.filter(pk=bc_pk, part=part).update(order=position)
        return Response({"detail": "Reordered."})


# ── Build ─────────────────────────────────────────────────────────────────────

class BuildTriggerView(APIView):
    """POST /api/books/<book_pk>/build/ — enqueue the build_book Celery task."""

    permission_classes = [IsAuthenticated]

    def post(self, request, book_pk):
        book = get_object_or_404(Book, pk=book_pk, user=request.user)
        if book.status == Book.Status.BUILDING:
            return Response({"detail": "Build already in progress."}, status=status.HTTP_409_CONFLICT)
        book.status = Book.Status.QUEUED
        book.save(update_fields=["status"])
        build_book.delay(book.pk)
        return Response({"detail": "Build queued.", "book_id": book.pk}, status=status.HTTP_202_ACCEPTED)


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

class LibraryView(generics.ListAPIView):
    """GET /api/library/ — completed books for the authenticated user."""

    permission_classes = [IsAuthenticated]
    serializer_class = BookListSerializer

    def get_queryset(self):
        return Book.objects.filter(user=self.request.user, status=Book.Status.COMPLETE)
