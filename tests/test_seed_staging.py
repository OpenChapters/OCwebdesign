"""Smoke test for the seed_staging management command."""

from io import StringIO

import pytest
from django.core.management import call_command

from catalog.models import Chapter, Example
from users.models import User


@pytest.mark.django_db
def test_seed_staging_creates_baseline():
    out = StringIO()
    call_command("seed_staging", stdout=out)

    assert User.objects.filter(email="admin@staging.local", is_staff=True).exists()
    assert User.objects.filter(email="author@staging.local", is_staff=False).exists()
    assert Chapter.objects.filter(chabbr="STG").exists()
    assert Example.objects.filter(statement_tex__startswith="What is").exists()


@pytest.mark.django_db
def test_seed_staging_is_idempotent():
    call_command("seed_staging", stdout=StringIO())
    call_command("seed_staging", stdout=StringIO())

    # Exactly one of each seeded object survives two runs.
    assert User.objects.filter(email="admin@staging.local").count() == 1
    assert Chapter.objects.filter(chabbr="STG").count() == 1
    assert Example.objects.filter(statement_tex__startswith="What is").count() == 1
