"""Shared pytest fixtures."""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tests.factories import (
    BookChapterFactory,
    BookFactory,
    BookPartFactory,
    BuildJobFactory,
    ChapterFactory,
    FoundationalChapterFactory,
    StaffUserFactory,
    UserFactory,
)


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def staff_user(db):
    return StaffUserFactory()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(user):
    """APIClient authenticated as a regular user."""
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def staff_client(staff_user):
    """APIClient authenticated as a staff user."""
    client = APIClient()
    token = RefreshToken.for_user(staff_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def chapter(db):
    return ChapterFactory()


@pytest.fixture
def foundational_chapter(db):
    return FoundationalChapterFactory()


@pytest.fixture
def book(user):
    return BookFactory(user=user)


@pytest.fixture
def book_with_parts(user):
    book = BookFactory(user=user)
    part1 = BookPartFactory(book=book, title="Part I", order=0)
    part2 = BookPartFactory(book=book, title="Part II", order=1)
    ch1 = ChapterFactory()
    ch2 = ChapterFactory()
    BookChapterFactory(part=part1, chapter=ch1, order=0)
    BookChapterFactory(part=part1, chapter=ch2, order=1)
    return book
