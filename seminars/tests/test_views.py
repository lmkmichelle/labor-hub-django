from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from seminars.models import Seminar, University


def make_seminar(visitor_name="Visitor", start_offset=1, end_offset=None,
                 university_name="Cornell", description="Details", countries=None):
    today = timezone.localdate()
    return Seminar.objects.create(
        visitor_name=visitor_name,
        visitor_email="v@example.com",
        university_name=university_name,
        visit_start=today + timedelta(days=start_offset),
        visit_end=today + timedelta(days=end_offset) if end_offset is not None else None,
        description=description,
        countries=countries or [],
    )


class SeminarsListViewTests(TestCase):
    def test_list_renders(self):
        response = self.client.get(reverse("seminars-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "seminars/seminars_list.html")

    def test_default_shows_upcoming_only(self):
        upcoming = make_seminar(visitor_name="Future", start_offset=5)
        past = make_seminar(visitor_name="Past", start_offset=-10, end_offset=-5)
        response = self.client.get(reverse("seminars-list"))
        self.assertIn(upcoming, response.context["seminars"])
        self.assertNotIn(past, response.context["seminars"])

    def test_show_archived_shows_past_only(self):
        upcoming = make_seminar(visitor_name="Future", start_offset=5)
        past = make_seminar(visitor_name="Past", start_offset=-10, end_offset=-5)
        response = self.client.get(reverse("seminars-list"), {"show_archived": "1"})
        self.assertIn(past, response.context["seminars"])
        self.assertNotIn(upcoming, response.context["seminars"])

    def test_search_filters_by_visitor_name(self):
        match = make_seminar(visitor_name="Labor Economist")
        other = make_seminar(visitor_name="Unrelated Scholar")
        response = self.client.get(reverse("seminars-list"), {"q": "Labor"})
        self.assertIn(match, response.context["seminars"])
        self.assertNotIn(other, response.context["seminars"])

    def test_country_filter(self):
        match = make_seminar(visitor_name="US Visit", countries=["US"])
        other = make_seminar(visitor_name="CA Visit", countries=["CA"])
        response = self.client.get(reverse("seminars-list"), {"countries": "US"})
        self.assertIn(match, response.context["seminars"])
        self.assertNotIn(other, response.context["seminars"])

    def test_filter_querystring_in_context(self):
        response = self.client.get(reverse("seminars-list"), {"q": "abc", "sort": "newest"})
        querystring = response.context["filter_querystring"]
        self.assertIn("q=abc", querystring)
        self.assertIn("sort=newest", querystring)

    def test_pagination_limits_to_ten(self):
        for i in range(11):
            make_seminar(visitor_name=f"Visitor {i}", start_offset=i + 1)
        response = self.client.get(reverse("seminars-list"))
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["seminars"]), 10)


class SeminarCreateViewTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="poster@example.com", password="testpass123",
            first_name="Post", last_name="Er", is_active=True,
        )

    def test_requires_login(self):
        response = self.client.get(reverse("seminar-create"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_authenticated_user_can_create(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("seminar-create"), {
            "country_code": "US",
            "visitor_name": "New Visitor",
            "visitor_email": "new@example.com",
            "visitor_affiliation": "",
            "university": "",
            "university_name": "Cornell University",
            "visit_start": timezone.localdate().isoformat(),
            "visit_end": "",
            "description": "A planned visit.",
        })
        self.assertEqual(Seminar.objects.count(), 1)
        seminar = Seminar.objects.get()
        self.assertEqual(seminar.posted_by, self.user)
        self.assertEqual(seminar.countries, ["US"])
        self.assertRedirects(response, reverse("seminars-list"))


class UniversitiesByCountryTests(TestCase):
    def test_invalid_country_returns_empty(self):
        response = self.client.get(reverse("seminar-universities"), {"country": "ZZ"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"universities": []})

    def test_known_country_returns_seeded_universities(self):
        University.objects.create(
            name="Cornell", country_code="US", source="manual", external_id="cornell",
        )
        response = self.client.get(reverse("seminar-universities"), {"country": "US"})
        names = [uni["name"] for uni in response.json()["universities"]]
        self.assertIn("Cornell", names)
