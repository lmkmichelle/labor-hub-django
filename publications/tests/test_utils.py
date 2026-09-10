import json

from django.test import RequestFactory, TestCase

from accounts.models import CustomUser
from publications.forms import PublicationForm
from publications.models import Author, Publication
from publications.utils import (
    handle_authors,
    handle_keywords,
    process_publication_form,
)


class HandleKeywordsTests(TestCase):
    def test_returns_plain_string_list(self):
        raw = json.dumps([{"value": "economics"}, {"value": "labor"}])
        self.assertEqual(handle_keywords(raw), ["economics", "labor"])

    def test_accepts_plain_strings(self):
        raw = json.dumps(["economics", "labor"])
        self.assertEqual(handle_keywords(raw), ["economics", "labor"])

    def test_skips_blank_entries(self):
        raw = json.dumps([{"value": "economics"}, {"value": "  "}, ""])
        self.assertEqual(handle_keywords(raw), ["economics"])

    def test_empty_list(self):
        self.assertEqual(handle_keywords("[]"), [])


class HandleAuthorsTests(TestCase):
    def test_matches_user_by_id(self):
        user = CustomUser.objects.create_user(
            email="a@example.com", password="pass12345",
            first_name="Jane", last_name="Doe", is_active=True,
        )
        raw = json.dumps([{"value": "Jane Doe", "id": str(user.id)}])
        authors = handle_authors(raw)
        self.assertEqual(len(authors), 1)
        self.assertEqual(authors[0].user, user)

    def test_matches_user_by_name_when_no_id(self):
        user = CustomUser.objects.create_user(
            email="b@example.com", password="pass12345",
            first_name="John", last_name="Smith", is_active=True,
        )
        raw = json.dumps([{"value": "john smith"}])
        authors = handle_authors(raw)
        self.assertEqual(authors[0].user, user)

    def test_creates_anonymous_author_when_no_match(self):
        raw = json.dumps([{"value": "Unknown Person"}])
        authors = handle_authors(raw)
        self.assertEqual(len(authors), 1)
        self.assertIsNone(authors[0].user)
        self.assertEqual(authors[0].name, "Unknown Person")
        self.assertTrue(Author.objects.filter(name="Unknown Person").exists())


class ProcessPublicationFormTests(TestCase):
    def test_topic_comes_from_cleaned_data_not_raw_post(self):
        data = {
            "title": "Study", "abstract": "a", "country_code": "US",
            "authors_input": '[{"value":"Jane Doe"}]',
            "topics_input": '[{"value":"labor supply"}]',
        }
        form = PublicationForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        request = RequestFactory().post("/publications/submit/", data)
        request.user = CustomUser(is_active=True)
        publication = process_publication_form(request, form)
        # Canonical casing from clean_topics_input, stored as a list.
        self.assertEqual(publication.topic, ["Labor Supply"])
        self.assertEqual(
            Publication.objects.get(pk=publication.pk).authors.count(), 1)
