"""Tests for the per-step BuildJob progress (BuildStep model + helpers).

The full build_book pipeline isn't exercised here — it requires git
clones and a TeX installation. Instead we test the BuildStep model,
the _build_step context manager that records lifecycle, the _reset_steps
helper that clears stale rows, and the serializer that exposes the
steps to /build/status/.
"""

import pytest

from books.models import BuildJob, BuildStep
from books.serializers import BuildJobSerializer
from books.tasks import _build_step, _reset_steps, _set_step_detail
from tests.factories import BookFactory, BuildJobFactory


@pytest.mark.django_db
class TestBuildStepModel:
    def test_default_status_pending(self, book):
        job = BuildJobFactory(book=book)
        step = BuildStep.objects.create(
            build_job=job, name="setup", label="Preparing workspace", order=0,
        )
        assert step.status == BuildStep.Status.PENDING

    def test_ordering(self, book):
        job = BuildJobFactory(book=book)
        BuildStep.objects.create(build_job=job, name="a", label="A", order=2)
        BuildStep.objects.create(build_job=job, name="b", label="B", order=0)
        BuildStep.objects.create(build_job=job, name="c", label="C", order=1)
        orders = list(
            BuildStep.objects.filter(build_job=job).values_list("name", flat=True)
        )
        assert orders == ["b", "c", "a"]

    def test_unique_order_per_job(self, book):
        from django.db import IntegrityError, transaction
        job = BuildJobFactory(book=book)
        BuildStep.objects.create(build_job=job, name="a", label="A", order=0)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                BuildStep.objects.create(build_job=job, name="b", label="B", order=0)


@pytest.mark.django_db
class TestBuildStepContextManager:
    def test_success_marks_succeeded(self, book):
        job = BuildJobFactory(book=book)
        log_lines: list[str] = []
        with _build_step(job, name="clone", label="Cloning", order=0, log_lines=log_lines):
            log_lines.append("did some work")

        step = BuildStep.objects.get(build_job=job, order=0)
        assert step.status == BuildStep.Status.SUCCEEDED
        assert step.started_at is not None
        assert step.finished_at is not None
        assert step.finished_at >= step.started_at
        assert step.log_tail == ""  # success path doesn't capture log

    def test_exception_marks_failed_and_reraises(self, book):
        job = BuildJobFactory(book=book)
        log_lines: list[str] = ["line 1", "line 2", "line 3"]

        with pytest.raises(ValueError, match="boom"):
            with _build_step(job, name="typeset", label="Typesetting",
                             order=0, log_lines=log_lines):
                raise ValueError("boom")

        step = BuildStep.objects.get(build_job=job, order=0)
        assert step.status == BuildStep.Status.FAILED
        assert step.finished_at is not None
        assert "ValueError" in step.detail
        assert "boom" in step.detail
        # log_tail should capture the recent log lines
        assert "line 3" in step.log_tail

    def test_detail_update_persists(self, book):
        job = BuildJobFactory(book=book)
        log_lines: list[str] = []
        with _build_step(job, name="clone", label="Cloning",
                         order=0, log_lines=log_lines) as step:
            _set_step_detail(step, "halfway")
            step.refresh_from_db()
            assert step.detail == "halfway"
            _set_step_detail(step, "almost done")

        step = BuildStep.objects.get(build_job=job, order=0)
        assert step.detail == "almost done"
        assert step.status == BuildStep.Status.SUCCEEDED

    def test_detail_truncated_to_500_chars(self, book):
        job = BuildJobFactory(book=book)
        log_lines: list[str] = []
        with _build_step(job, name="x", label="X", order=0, log_lines=log_lines) as step:
            _set_step_detail(step, "a" * 1000)

        step = BuildStep.objects.get(build_job=job, order=0)
        assert len(step.detail) == 500

    def test_log_tail_bounded(self, book):
        """Failures with a very long log should bound log_tail."""
        job = BuildJobFactory(book=book)
        log_lines = [f"line {i}" * 100 for i in range(200)]

        with pytest.raises(RuntimeError):
            with _build_step(job, name="x", label="X", order=0, log_lines=log_lines):
                raise RuntimeError("oops")

        step = BuildStep.objects.get(build_job=job, order=0)
        assert len(step.log_tail) <= 8000


@pytest.mark.django_db
class TestResetSteps:
    def test_clears_existing_steps(self, book):
        job = BuildJobFactory(book=book)
        BuildStep.objects.create(build_job=job, name="a", label="A", order=0)
        BuildStep.objects.create(build_job=job, name="b", label="B", order=1)
        assert BuildStep.objects.filter(build_job=job).count() == 2

        _reset_steps(job)
        assert BuildStep.objects.filter(build_job=job).count() == 0

    def test_does_not_touch_other_jobs(self, user):
        from tests.factories import BookFactory
        book_a = BookFactory(user=user)
        book_b = BookFactory(user=user)
        job_a = BuildJobFactory(book=book_a)
        job_b = BuildJobFactory(book=book_b)
        BuildStep.objects.create(build_job=job_a, name="a", label="A", order=0)
        BuildStep.objects.create(build_job=job_b, name="b", label="B", order=0)

        _reset_steps(job_a)
        assert BuildStep.objects.filter(build_job=job_a).count() == 0
        assert BuildStep.objects.filter(build_job=job_b).count() == 1


@pytest.mark.django_db
class TestBuildStatusEndpoint:
    def test_steps_included_in_status_response(self, auth_client, book):
        job = BuildJobFactory(book=book)
        BuildStep.objects.create(
            build_job=job, name="clone", label="Cloning chapter sources",
            order=0, status=BuildStep.Status.SUCCEEDED, detail="2 repositories",
        )
        BuildStep.objects.create(
            build_job=job, name="typeset", label="Typesetting",
            order=1, status=BuildStep.Status.RUNNING, detail="pdflatex pass 2",
        )

        resp = auth_client.get(f"/api/books/{book.id}/build/status/")
        assert resp.status_code == 200
        assert "build_job" in resp.data
        steps = resp.data["build_job"]["steps"]
        assert len(steps) == 2
        assert [s["name"] for s in steps] == ["clone", "typeset"]
        assert steps[0]["status"] == "succeeded"
        assert steps[1]["status"] == "running"
        assert steps[1]["detail"] == "pdflatex pass 2"

    def test_status_response_when_no_build_yet(self, auth_client, book):
        resp = auth_client.get(f"/api/books/{book.id}/build/status/")
        assert resp.status_code == 200
        assert "build_job" not in resp.data


@pytest.mark.django_db
class TestSerializer:
    def test_serializer_shape(self, book):
        job = BuildJobFactory(book=book)
        BuildStep.objects.create(
            build_job=job, name="setup", label="Preparing workspace",
            order=0, status=BuildStep.Status.SUCCEEDED,
        )
        data = BuildJobSerializer(job).data
        assert "steps" in data
        assert len(data["steps"]) == 1
        step = data["steps"][0]
        assert set(step.keys()) == {
            "name", "label", "order", "status",
            "detail", "started_at", "finished_at", "log_tail",
        }
