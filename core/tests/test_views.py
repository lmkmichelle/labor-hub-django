"""View tests for the core app.

Includes the original lightweight Flowbite-cleanup smoke tests (page renders on
an empty database) plus behavioral coverage of the home context, map, JSON API
endpoints, account list views, and search.
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from events.models import Event
from publications.models import Author, Publication
from seminars.models import Seminar


def make_user(email="user@example.com", first_name="Jane", last_name="Doe",
              role=CustomUser.Role.RESEARCHER, country_code="US"):
    user = CustomUser.objects.create_user(
        email=email, password="pass12345",
        first_name=first_name, last_name=last_name, role=role, is_active=True,
    )
    user.profile.country_code = country_code
    user.profile.position = "Professor"
    user.profile.save()
    return user


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


class HomeContextTests(TestCase):
    def test_home_context_includes_recent_content(self):
        host = make_user(email="host@example.com")
        Event.objects.create(
            title="Upcoming Conf", description="d",
            date=timezone.now() + timedelta(days=3),
            location="Ithaca", status="approved", host=host,
        )
        Seminar.objects.create(
            title="Upcoming Visit", host=host,
            date=timezone.now() + timedelta(days=4),
            location="Ithaca", description="d",
        )
        publication = Publication.objects.create(
            title="Recent Paper", abstract="a",
            study_url="https://example.com", status="approved",
        )
        publication.authors.add(Author.objects.create(user=host, name="Host User"))

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        titles = [e["title"] for e in response.context["upcoming_events"]]
        self.assertIn("Upcoming Conf", titles)
        seminar_titles = [s["title"] for s in response.context["upcoming_seminars"]]
        self.assertIn("Upcoming Visit", seminar_titles)
        paper_titles = [p["title"] for p in response.context["recent_papers"]]
        self.assertIn("Recent Paper", paper_titles)


class MapViewTests(TestCase):
    def test_map_renders(self):
        response = self.client.get(reverse("map"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/map.html")


class CountriesApiTests(TestCase):
    def test_countries_with_users(self):
        make_user(email="us@example.com", country_code="US")
        response = self.client.get(reverse("countries_with_users"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("US", data)
        self.assertEqual(data["US"][0]["email"], "us@example.com")

    def test_countries_with_papers(self):
        publication = Publication.objects.create(
            title="Paper", abstract="a", study_url="https://example.com",
            status="approved", country_code="US",
        )
        publication.authors.add(Author.objects.create(user=None, name="Anon"))
        response = self.client.get(reverse("countries_with_papers"))
        data = response.json()
        self.assertIn("US", data)
        self.assertEqual(data["US"][0]["title"], "Paper")


class SearchAccountsTests(TestCase):
    def test_search_returns_matching_users(self):
        make_user(email="jane@example.com", first_name="Jane", last_name="Doe")
        response = self.client.get(reverse("search_accounts"), {"q": "Jane"})
        data = response.json()
        self.assertTrue(any(item["value"] == "Jane Doe" for item in data))


class PublicationsListViewTests(TestCase):
    def test_only_approved_publications_shown(self):
        approved = Publication.objects.create(
            title="Approved", abstract="a", study_url="https://example.com",
            status="approved",
        )
        pending = Publication.objects.create(
            title="Pending", abstract="a", study_url="https://example.com",
            status="pending",
        )
        response = self.client.get(reverse("publications"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "publications/publications.html")
        self.assertIn(approved, response.context["publications"])
        self.assertNotIn(pending, response.context["publications"])


class UserListViewTests(TestCase):
    def test_researchers_list_shows_only_researchers(self):
        researcher = make_user(email="r@example.com", role=CustomUser.Role.RESEARCHER)
        student = make_user(email="s@example.com", role=CustomUser.Role.STUDENT)
        response = self.client.get(reverse("researchers"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(researcher, response.context["users"])
        self.assertNotIn(student, response.context["users"])

    def test_students_list_shows_only_students(self):
        researcher = make_user(email="r@example.com", role=CustomUser.Role.RESEARCHER)
        student = make_user(email="s@example.com", role=CustomUser.Role.STUDENT)
        response = self.client.get(reverse("students"))
        self.assertIn(student, response.context["users"])
        self.assertNotIn(researcher, response.context["users"])

    def test_name_search_filters_results(self):
        match = make_user(email="match@example.com", first_name="Alice", last_name="Smith")
        other = make_user(email="other@example.com", first_name="Bob", last_name="Jones")
        response = self.client.get(
            reverse("researchers"), {"q": "Alice", "filter": "name"})
        self.assertIn(match, response.context["users"])
        self.assertNotIn(other, response.context["users"])
