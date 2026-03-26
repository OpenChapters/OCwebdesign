import shutil
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import Count, Q
from django.http import FileResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Chapter

from .models import AuditEntry, SiteSetting

from .permissions import IsStaffUser
from .serializers import (
    AdminChapterSerializer,
    AdminUserCreateSerializer,
    AdminUserDetailSerializer,
    AdminUserListSerializer,
)

User = get_user_model()


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardView(APIView):
    """GET /api/admin/dashboard/ — aggregated platform stats."""

    permission_classes = [IsStaffUser]

    def get(self, request):
        from books.models import Book, BuildJob

        now = timezone.now()
        week_ago = now - timedelta(days=7)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total_users = User.objects.count()
        new_users_week = User.objects.filter(date_joined__gte=week_ago).count()

        published_chapters = Chapter.objects.filter(published=True).count()
        unpublished_chapters = Chapter.objects.filter(published=False).count()

        book_counts = dict(
            Book.objects.values_list("status").annotate(c=Count("id")).values_list("status", "c")
        )

        builds_today = BuildJob.objects.filter(started_at__gte=today_start)
        builds_today_count = builds_today.count()
        builds_today_ok = builds_today.filter(error_message="").count()
        builds_today_fail = builds_today_count - builds_today_ok

        recent_builds = []
        for job in BuildJob.objects.select_related("book", "book__user").order_by("-id")[:10]:
            recent_builds.append({
                "id": job.id,
                "book_title": job.book.title,
                "user_email": job.book.user.email,
                "status": job.book.status,
                "started_at": job.started_at,
                "finished_at": job.finished_at,
                "error": bool(job.error_message),
            })

        pdf_dir = Path(str(settings.BUILD_OUTPUT_DIR))
        pdf_count = 0
        pdf_size_bytes = 0
        if pdf_dir.is_dir():
            for f in pdf_dir.glob("*.pdf"):
                pdf_count += 1
                pdf_size_bytes += f.stat().st_size

        return Response({
            "users": {"total": total_users, "new_this_week": new_users_week},
            "chapters": {"published": published_chapters, "unpublished": unpublished_chapters},
            "books": {
                "draft": book_counts.get("draft", 0),
                "queued": book_counts.get("queued", 0),
                "building": book_counts.get("building", 0),
                "complete": book_counts.get("complete", 0),
                "failed": book_counts.get("failed", 0),
            },
            "builds_today": {"total": builds_today_count, "success": builds_today_ok, "failed": builds_today_fail},
            "storage": {"pdf_count": pdf_count, "pdf_size_mb": round(pdf_size_bytes / (1024 * 1024), 1)},
            "recent_builds": recent_builds,
        })


class WorkersView(APIView):
    """GET /api/admin/workers/ — Celery worker status."""

    permission_classes = [IsStaffUser]

    def get(self, request):
        try:
            from ocweb.celery import app as celery_app

            inspect = celery_app.control.inspect(timeout=3)
            ping = inspect.ping() or {}
            active = inspect.active() or {}
            stats = inspect.stats() or {}

            workers = []
            for name in ping:
                worker_active = active.get(name, [])
                worker_stats = stats.get(name, {})
                workers.append({
                    "name": name,
                    "status": "online",
                    "active_tasks": len(worker_active),
                    "total_tasks": worker_stats.get("total", {}),
                    "pool": worker_stats.get("pool", {}).get("implementation", ""),
                    "concurrency": worker_stats.get("pool", {}).get("max-concurrency", 0),
                })
            return Response({"workers": workers})
        except Exception as e:
            return Response({"workers": [], "error": f"Could not connect to Celery: {e}"})


# ── User Management ───────────────────────────────────────────────────────────

class AdminUserListView(generics.ListCreateAPIView):
    """GET /api/admin/users/ — paginated user list with search.
    POST /api/admin/users/ — create a new user."""

    permission_classes = [IsStaffUser]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminUserCreateSerializer
        return AdminUserListSerializer

    def get_queryset(self):
        qs = User.objects.annotate(book_count=Count("books")).order_by("-date_joined")
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(email__icontains=search)
        return qs

    def perform_create(self, serializer):
        user = serializer.save()
        AuditEntry.log(self.request, "user.create", "User", user.id, {"email": user.email})


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/admin/users/<id>/"""

    permission_classes = [IsStaffUser]
    serializer_class = AdminUserDetailSerializer
    queryset = User.objects.all()

    def perform_update(self, serializer):
        user = self.get_object()
        changes = {k: {"old": getattr(user, k), "new": v} for k, v in serializer.validated_data.items() if getattr(user, k) != v}
        serializer.save()
        if changes:
            AuditEntry.log(self.request, "user.update", "User", user.id, changes)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user.id == request.user.id:
            return Response(
                {"detail": "You cannot delete your own account from the admin panel."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        AuditEntry.log(request, "user.delete", "User", user.id, {"email": user.email})
        return super().destroy(request, *args, **kwargs)


class AdminUserBooksView(APIView):
    """GET /api/admin/users/<id>/books/ — list a user's books."""

    permission_classes = [IsStaffUser]

    def get(self, request, pk):
        from books.models import Book

        user = generics.get_object_or_404(User, pk=pk)
        books = Book.objects.filter(user=user).order_by("-created_at")
        data = [
            {
                "id": b.id,
                "title": b.title,
                "status": b.status,
                "created_at": b.created_at,
                "updated_at": b.updated_at,
            }
            for b in books
        ]
        return Response(data)


# ── Chapter Management ────────────────────────────────────────────────────────

class AdminChapterListView(generics.ListAPIView):
    """GET /api/admin/chapters/ — all chapters including unpublished."""

    permission_classes = [IsStaffUser]
    serializer_class = AdminChapterSerializer

    def get_queryset(self):
        qs = Chapter.objects.all().order_by("title")
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(chabbr__icontains=search)
                | Q(keywords__icontains=search)
            )
        return qs


class AdminChapterDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/admin/chapters/<id>/ — view and edit chapter metadata."""

    permission_classes = [IsStaffUser]
    serializer_class = AdminChapterSerializer
    queryset = Chapter.objects.all()

    def perform_update(self, serializer):
        ch = self.get_object()
        changes = {k: {"old": getattr(ch, k), "new": v} for k, v in serializer.validated_data.items() if getattr(ch, k) != v}
        serializer.save()
        if changes:
            AuditEntry.log(self.request, "chapter.update", "Chapter", ch.id, changes)


class AdminChapterSyncView(APIView):
    """POST /api/admin/chapters/sync/ — trigger a chapter sync from GitHub."""

    permission_classes = [IsStaffUser]

    def post(self, request):
        from io import StringIO

        out = StringIO()
        try:
            call_command("sync_chapters", stdout=out, stderr=out)
            return Response({"detail": "Sync completed.", "output": out.getvalue()})
        except Exception as e:
            return Response(
                {"detail": f"Sync failed: {e}", "output": out.getvalue()},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ── Build Management ──────────────────────────────────────────────────────────

class AdminBuildListView(APIView):
    """GET /api/admin/builds/ — paginated build list with filters."""

    permission_classes = [IsStaffUser]

    def get(self, request):
        from books.models import BuildJob

        qs = BuildJob.objects.select_related("book", "book__user").order_by("-id")

        # Filters
        status_filter = request.query_params.get("status", "").strip()
        if status_filter:
            qs = qs.filter(book__status=status_filter)
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(book__title__icontains=search) | Q(book__user__email__icontains=search)
            )

        # Simple pagination
        page = int(request.query_params.get("page", 1))
        page_size = 25
        total = qs.count()
        offset = (page - 1) * page_size
        jobs = qs[offset:offset + page_size]

        results = []
        for job in jobs:
            pdf_path = Path(job.pdf_path) if job.pdf_path else None
            results.append({
                "id": job.id,
                "book_id": job.book.id,
                "book_title": job.book.title,
                "user_email": job.book.user.email,
                "status": job.book.status,
                "celery_task_id": job.celery_task_id,
                "started_at": job.started_at,
                "finished_at": job.finished_at,
                "has_error": bool(job.error_message),
                "pdf_size_mb": round(pdf_path.stat().st_size / (1024 * 1024), 1) if pdf_path and pdf_path.is_file() else None,
            })

        return Response({
            "count": total,
            "page": page,
            "page_size": page_size,
            "results": results,
        })


class AdminBuildDetailView(APIView):
    """GET /api/admin/builds/<id>/ — build detail with full log."""

    permission_classes = [IsStaffUser]

    def get(self, request, pk):
        from books.models import BuildJob

        job = generics.get_object_or_404(
            BuildJob.objects.select_related("book", "book__user"), pk=pk
        )
        return Response({
            "id": job.id,
            "book_id": job.book.id,
            "book_title": job.book.title,
            "user_email": job.book.user.email,
            "status": job.book.status,
            "celery_task_id": job.celery_task_id,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "log_output": job.log_output,
            "error_message": job.error_message,
            "pdf_path": job.pdf_path,
        })


class AdminBuildCancelView(APIView):
    """POST /api/admin/builds/<id>/cancel/ — revoke a queued/building task."""

    permission_classes = [IsStaffUser]

    def post(self, request, pk):
        from books.models import Book, BuildJob

        job = generics.get_object_or_404(BuildJob, pk=pk)
        if job.book.status not in (Book.Status.QUEUED, Book.Status.BUILDING):
            return Response(
                {"detail": "Build is not in a cancellable state."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Revoke the Celery task
        if job.celery_task_id:
            from ocweb.celery import app as celery_app
            celery_app.control.revoke(job.celery_task_id, terminate=True)

        job.book.status = Book.Status.FAILED
        job.book.save(update_fields=["status"])
        job.error_message = "Cancelled by admin."
        job.finished_at = timezone.now()
        job.save(update_fields=["error_message", "finished_at"])

        AuditEntry.log(request, "build.cancel", "BuildJob", job.id, {"book": job.book.title})
        return Response({"detail": "Build cancelled."})


class AdminBuildRetryView(APIView):
    """POST /api/admin/builds/<id>/retry/ — re-enqueue a failed build."""

    permission_classes = [IsStaffUser]

    def post(self, request, pk):
        from books.models import Book, BuildJob
        from books.tasks import build_book

        job = generics.get_object_or_404(BuildJob, pk=pk)
        if job.book.status not in (Book.Status.FAILED, Book.Status.COMPLETE):
            return Response(
                {"detail": "Only failed or complete builds can be retried."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        job.book.status = Book.Status.QUEUED
        job.book.save(update_fields=["status"])
        build_book.delay(job.book.id)
        AuditEntry.log(request, "build.retry", "BuildJob", job.id, {"book": job.book.title})
        return Response({"detail": "Build re-queued."})


class AdminBuildDownloadView(APIView):
    """GET /api/admin/builds/<id>/download/ — download any user's PDF."""

    permission_classes = [IsStaffUser]

    def get(self, request, pk):
        from books.models import BuildJob

        job = generics.get_object_or_404(BuildJob, pk=pk)
        pdf = Path(job.pdf_path) if job.pdf_path else None
        if not pdf or not pdf.is_file():
            return Response({"detail": "PDF not found."}, status=status.HTTP_404_NOT_FOUND)

        filename = f"{job.book.title}.pdf".replace("/", "-")
        return FileResponse(open(pdf, "rb"), content_type="application/pdf",
                            as_attachment=True, filename=filename)


# ── System Monitoring ─────────────────────────────────────────────────────────

class SystemHealthView(APIView):
    """GET /api/admin/system/health/ — health checks for all services."""

    permission_classes = [IsStaffUser]

    def get(self, request):
        checks = {}

        # PostgreSQL
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            checks["postgresql"] = {"status": "ok"}
        except Exception as e:
            checks["postgresql"] = {"status": "error", "detail": str(e)}

        # RabbitMQ (via Celery ping)
        try:
            from ocweb.celery import app as celery_app
            ping = celery_app.control.inspect(timeout=3).ping()
            if ping:
                checks["rabbitmq"] = {"status": "ok"}
            else:
                checks["rabbitmq"] = {"status": "error", "detail": "No workers responded"}
        except Exception as e:
            checks["rabbitmq"] = {"status": "error", "detail": str(e)}

        # Celery workers
        try:
            from ocweb.celery import app as celery_app
            inspect = celery_app.control.inspect(timeout=3)
            active = inspect.active() or {}
            reserved = inspect.reserved() or {}
            worker_count = len(active)
            active_tasks = sum(len(t) for t in active.values())
            queued_tasks = sum(len(t) for t in reserved.values())
            checks["celery"] = {
                "status": "ok" if worker_count > 0 else "warning",
                "workers": worker_count,
                "active_tasks": active_tasks,
                "queued_tasks": queued_tasks,
            }
        except Exception as e:
            checks["celery"] = {"status": "error", "detail": str(e)}

        # Disk space
        try:
            usage = shutil.disk_usage("/")
            free_gb = round(usage.free / (1024 ** 3), 1)
            total_gb = round(usage.total / (1024 ** 3), 1)
            used_pct = round((usage.used / usage.total) * 100, 1)
            checks["disk"] = {
                "status": "ok" if used_pct < 90 else "warning",
                "free_gb": free_gb,
                "total_gb": total_gb,
                "used_percent": used_pct,
            }
        except Exception as e:
            checks["disk"] = {"status": "error", "detail": str(e)}

        # PDF storage
        pdf_dir = Path(str(settings.BUILD_OUTPUT_DIR))
        pdf_count = 0
        pdf_size_bytes = 0
        oldest = None
        newest = None
        if pdf_dir.is_dir():
            for f in pdf_dir.glob("*.pdf"):
                pdf_count += 1
                st = f.stat()
                pdf_size_bytes += st.st_size
                mtime = st.st_mtime
                if oldest is None or mtime < oldest:
                    oldest = mtime
                if newest is None or mtime > newest:
                    newest = mtime
        checks["pdf_storage"] = {
            "status": "ok",
            "count": pdf_count,
            "size_mb": round(pdf_size_bytes / (1024 * 1024), 1),
            "oldest": timezone.datetime.fromtimestamp(oldest).isoformat() if oldest else None,
            "newest": timezone.datetime.fromtimestamp(newest).isoformat() if newest else None,
        }

        # Overall status
        statuses = [c.get("status", "ok") for c in checks.values() if isinstance(c, dict) and "status" in c]
        if "error" in statuses:
            overall = "error"
        elif "warning" in statuses:
            overall = "warning"
        else:
            overall = "ok"

        return Response({"overall": overall, "checks": checks})


class SystemGitHubView(APIView):
    """GET /api/admin/system/github/ — GitHub token status and rate limit."""

    permission_classes = [IsStaffUser]

    def get(self, request):
        import httpx

        token = getattr(settings, "GITHUB_TOKEN", "")
        if not token:
            return Response({
                "status": "not_configured",
                "detail": "GITHUB_TOKEN is not set.",
            })

        try:
            resp = httpx.get(
                "https://api.github.com/rate_limit",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.status_code == 401:
                return Response({
                    "status": "invalid",
                    "detail": "Token is invalid or expired.",
                })
            data = resp.json()
            core = data.get("resources", {}).get("core", {})
            return Response({
                "status": "ok",
                "rate_limit": core.get("limit", 0),
                "remaining": core.get("remaining", 0),
                "reset_at": timezone.datetime.fromtimestamp(
                    core.get("reset", 0)
                ).isoformat() if core.get("reset") else None,
            })
        except Exception as e:
            return Response({
                "status": "error",
                "detail": str(e),
            })


# ── Site Settings ─────────────────────────────────────────────────────────────

class AdminSettingsView(APIView):
    """GET /api/admin/settings/ — list all settings.
    PATCH /api/admin/settings/ — update one or more settings."""

    permission_classes = [IsStaffUser]

    def get(self, request):
        return Response(SiteSetting.get_all())

    def patch(self, request):
        updated = []
        for key, value in request.data.items():
            if key not in SiteSetting.DEFAULTS:
                continue
            obj, _ = SiteSetting.objects.update_or_create(
                key=key,
                defaults={"value": value, "updated_by": request.user},
            )
            updated.append(key)
        if updated:
            AuditEntry.log(request, "settings.update", "SiteSetting", detail={"keys": updated})
        return Response({"detail": f"Updated: {', '.join(updated)}", "settings": SiteSetting.get_all()})


class PublicSettingsView(APIView):
    """GET /api/settings/public/ — public settings (no auth)."""

    permission_classes = []
    authentication_classes = []

    def get(self, request):
        all_settings = SiteSetting.get_all()
        return Response({
            "site_name": all_settings.get("site_name", "OpenChapters"),
            "announcement_banner": all_settings.get("announcement_banner", ""),
            "registration_enabled": all_settings.get("registration_enabled", True),
        })


# ── Audit Log ─────────────────────────────────────────────────────────────────

class AdminAuditLogView(APIView):
    """GET /api/admin/audit/ — paginated audit log with filters."""

    permission_classes = [IsStaffUser]

    def get(self, request):
        qs = AuditEntry.objects.select_related("user").order_by("-timestamp")

        # Filters
        action = request.query_params.get("action", "").strip()
        if action:
            qs = qs.filter(action__icontains=action)
        target_type = request.query_params.get("target_type", "").strip()
        if target_type:
            qs = qs.filter(target_type=target_type)
        user_email = request.query_params.get("user", "").strip()
        if user_email:
            qs = qs.filter(user__email__icontains=user_email)

        page = int(request.query_params.get("page", 1))
        page_size = 30
        total = qs.count()
        offset = (page - 1) * page_size
        entries = qs[offset:offset + page_size]

        results = [
            {
                "id": e.id,
                "timestamp": e.timestamp,
                "user_email": e.user.email if e.user else None,
                "action": e.action,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "detail": e.detail,
                "ip_address": e.ip_address,
            }
            for e in entries
        ]

        return Response({
            "count": total,
            "page": page,
            "page_size": page_size,
            "results": results,
        })


# ── Analytics ─────────────────────────────────────────────────────────────────

class AdminAnalyticsBuildsView(APIView):
    """GET /api/admin/analytics/builds/ — build counts by day for the last 30 days."""

    permission_classes = [IsStaffUser]

    def get(self, request):
        from books.models import BuildJob
        from django.db.models.functions import TruncDate

        days = int(request.query_params.get("days", 30))
        since = timezone.now() - timedelta(days=days)

        qs = (
            BuildJob.objects.filter(started_at__gte=since)
            .annotate(date=TruncDate("started_at"))
            .values("date")
            .annotate(
                total=Count("id"),
                success=Count("id", filter=Q(error_message="")),
                failed=Count("id", filter=~Q(error_message="")),
            )
            .order_by("date")
        )
        return Response(list(qs))


class AdminAnalyticsChaptersView(APIView):
    """GET /api/admin/analytics/chapters/ — most popular chapters by inclusion count."""

    permission_classes = [IsStaffUser]

    def get(self, request):
        from books.models import BookChapter

        qs = (
            BookChapter.objects.values("chapter__title", "chapter__chabbr")
            .annotate(count=Count("id"))
            .order_by("-count")[:20]
        )
        return Response([
            {"title": r["chapter__title"], "chabbr": r["chapter__chabbr"], "count": r["count"]}
            for r in qs
        ])


class AdminAnalyticsUsersView(APIView):
    """GET /api/admin/analytics/users/ — registration trend for the last 90 days."""

    permission_classes = [IsStaffUser]

    def get(self, request):
        from django.db.models.functions import TruncDate

        days = int(request.query_params.get("days", 90))
        since = timezone.now() - timedelta(days=days)

        qs = (
            User.objects.filter(date_joined__gte=since)
            .annotate(date=TruncDate("date_joined"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )
        return Response(list(qs))
