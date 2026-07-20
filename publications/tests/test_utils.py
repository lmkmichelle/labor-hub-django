import json

from django.test import TestCase

from accounts.models import CustomUser
from publications.models import Author
from publications.utils import handle_authors, handle_keywords


class HandleKeywordsTests(TestCase):
    def test_returns_entries_as_list(self):
        raw = json.dumps([{"value": "economics"}, {"value": "labor"}])
        self.assertEqual(
            handle_keywords(raw),
            [{"value": "economics"}, {"value": "labor"}],
        )

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
