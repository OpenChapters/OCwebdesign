"""Model factories for tests using factory_boy."""

import factory
from django.contrib.auth import get_user_model

from books.models import Book, BookChapter, BookPart, BuildJob
from catalog.models import Chapter, Example, ExampleFigure, ExampleVersion

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


class ExampleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Example
        skip_postgeneration_save = True

    author = factory.SubFactory(UserFactory)
    primary_chapter = factory.SubFactory(ChapterFactory)
    statement_tex = factory.Sequence(lambda n: f"Statement {n}: prove that 2+2={2+2}.")
    solution_tex = factory.Sequence(lambda n: f"Solution {n}: by direct calculation.")
    difficulty = Example.Difficulty.STANDARD
    status = Example.Status.DRAFT

    @factory.post_generation
    def chapters(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for ch in extracted:
                self.chapters.add(ch)
        else:
            # Default: tag the example to its primary chapter only.
            self.chapters.add(self.primary_chapter)


class PublishedExampleFactory(ExampleFactory):
    status = Example.Status.PUBLISHED


class ExampleFigureFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ExampleFigure

    example = factory.SubFactory(ExampleFactory)
    file = factory.django.FileField(filename="figure.png", data=b"\x89PNG\r\n\x1a\n")
    original_filename = "figure.png"
    order = 0


class ExampleVersionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ExampleVersion

    example = factory.SubFactory(ExampleFactory)
    version_no = factory.Sequence(lambda n: n + 1)
    snapshot = factory.LazyFunction(
        lambda: {
            "statement_tex": "old statement",
            "solution_tex": "old solution",
            "difficulty": "standard",
            "primary_chapter_chabbr": None,
            "chapters_chabbrs": [],
            "status": "draft",
            "slug": None,
        }
    )
