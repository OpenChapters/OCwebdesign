"""Model factories for tests using factory_boy."""

import factory
from django.contrib.auth import get_user_model

from books.models import Book, BookChapter, BookPart, BuildJob
from catalog.models import Chapter

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@test.com")
    username = factory.LazyAttribute(lambda o: o.email)
    full_name = factory.Faker("name")
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Use create_user to properly hash the password."""
        manager = cls._get_manager(model_class)
        return manager.create_user(*args, password="testpass123", **kwargs)


class StaffUserFactory(UserFactory):
    is_staff = True


class ChapterFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Chapter

    github_repo = "OpenChapters/OpenChapters"
    chapter_subdir = factory.Sequence(lambda n: f"src/TestChapter{n}")
    title = factory.Sequence(lambda n: f"Test Chapter {n}")
    authors = factory.LazyFunction(lambda: ["Test Author"])
    toc = factory.LazyFunction(lambda: ["Section 1", "Section 2"])
    latex_entry_file = factory.LazyAttribute(lambda o: f"{o.chapter_subdir}/test.tex")
    chabbr = factory.Sequence(lambda n: f"TC{n:04d}")
    chapter_type = "topical"
    published = True


class FoundationalChapterFactory(ChapterFactory):
    chapter_type = "foundational"
    depends_on = factory.LazyFunction(list)


class BookFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Book

    user = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"Test Book {n}")
    status = Book.Status.DRAFT


class BookPartFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BookPart

    book = factory.SubFactory(BookFactory)
    title = factory.Sequence(lambda n: f"Part {n}")
    order = factory.Sequence(lambda n: n)


class BookChapterFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BookChapter

    part = factory.SubFactory(BookPartFactory)
    chapter = factory.SubFactory(ChapterFactory)
    order = factory.Sequence(lambda n: n)


class BuildJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BuildJob

    book = factory.SubFactory(BookFactory)
    celery_task_id = factory.Faker("uuid4")
