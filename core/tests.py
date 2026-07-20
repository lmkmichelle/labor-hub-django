"""Lightweight view smoke tests.

These guard the Flowbite frontend cleanup (a presentation-only refactor): they
assert that key pages still return HTTP 200 and render the expected template on
an empty database (exercising the shared empty-state path). They are an OPTIONAL
regression net, not behavior-driven TDD, so they intentionally avoid asserting on
specific markup that the refactor is allowed to change.
"""

from django.test import TestCase
from django.urls import reverse


class SmokeTestBase(TestCase):
    """Shared base for the cleanup's view smoke tests."""


class HomeSmokeTests(SmokeTestBase):
    def test_home_page_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")


class SeminarsSmokeTests(SmokeTestBase):
    def test_seminars_list_renders(self):
        response = self.client.get(reverse("seminars-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "seminars/seminars_list.html")

    def test_seminars_list_pagination_request_renders(self):
        response = self.client.get(reverse("seminars-list"), {"page": 1})
        self.assertEqual(response.status_code, 200)
