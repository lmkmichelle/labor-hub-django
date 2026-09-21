import datetime

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from publications.citations import build_bibtex, cite_key, format_author_name
from publications.models import Author, Publication


def make_user(email="author@example.com", first_name="Jane", last_name="Doe"):
    return CustomUser.objects.create_user(
        email=email, password="pass12345",
        first_name=first_name, last_name=last_name, is_active=True,
    )


def make_publication(**overrides):
    fields = dict(title="A Study", abstract="Abstract text.", status="approved")
    fields.update(overrides)
    return Publication.objects.create(**fields)


class FormatAuthorNameTests(TestCase):
    def test_linked_user_reorders_to_last_first(self):
        user = make_user(first_name="Jason", last_name="Sockin")
        author = Author.objects.create(user=user, name="ignored")
        self.assertEqual(format_author_name(author), "Sockin, Jason")

    def test_free_text_two_word_name_reorders(self):
        author = Author.objects.create(name="Jason Sockin")
        self.assertEqual(format_author_name(author), "Sockin, Jason")

    def test_free_text_multi_word_first_name_keeps_all_but_last_token(self):
        author = Author.objects.create(name="Mary Jane Watson")
        self.assertEqual(format_author_name(author), "Watson, Mary Jane")

    def test_single_token_name_is_unchanged(self):
        author = Author.objects.create(name="Cher")
        self.assertEqual(format_author_name(author), "Cher")


class CiteKeyTests(TestCase):
    def test_regular_paper_key(self):
        publication = make_publication(status="pending")
        publication.discussion_paper_number = 5
        self.assertEqual(cite_key(publication), "LaborHubDP5")

    def test_job_market_paper_key(self):
        publication = make_publication(status="pending", is_job_market=True)
        publication.job_market_paper_number = 3
        self.assertEqual(cite_key(publication), "LaborHubJ3")


class BuildBibtexTests(TestCase):
    def test_includes_expected_fields(self):
        publication = make_publication(
            title="Job Ads as Signals",
            abstract="We test this assumption.",
        )
        publication.discussion_paper_number = 5
        publication.applied_at = timezone.make_aware(datetime.datetime(2026, 7, 14))
        publication.authors.add(Author.objects.create(name="Jason Sockin"))
        publication.authors.add(Author.objects.create(name="Pawel Adrjan"))

        body = build_bibtex(publication, "https://laborhub.example.com/publications/1/")

        self.assertIn("% WARNING: This file may contain UTF-8", body)
        self.assertIn("@techreport{LaborHubDP5,", body)
        self.assertIn('title = "Job Ads as Signals",', body)
        self.assertIn('author = "Sockin, Jason and Adrjan, Pawel",', body)
        self.assertIn('institution = "Cornell University ILR School",', body)
        self.assertIn(' type = "Discussion Paper",', body)
        self.assertIn(' series = "Labor Hub Discussion Paper Series",', body)
        self.assertIn(' number = "5",', body)
        self.assertIn(' year = "2026",', body)
        self.assertIn(' month = "July",', body)
        self.assertIn(' URL = "https://laborhub.example.com/publications/1/",', body)
        self.assertIn("abstract = {We test this assumption.},", body)

    def test_escapes_ampersand_and_quotes_in_title(self):
        publication = make_publication(title='Wages & "Beliefs"')
        publication.discussion_paper_number = 1
        body = build_bibtex(publication, "https://example.com/1/")
        self.assertIn(r"Wages \& ''Beliefs''", body)
