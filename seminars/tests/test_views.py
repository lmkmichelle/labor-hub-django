from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from seminars.models import Seminar, University


def make_seminar(visitor_name="Visitor", start_offset=1, end_offset=None,
                 university_name="Cornell", description="Details", countries=None,
                 status="approved"):
    today = timezone.localdate()
    return Seminar.objects.create(
        visitor_name=visitor_name,
        visitor_email="v@example.com",
        university_name=university_name,
        visit_start=today + timedelta(days=start_offset),
        visit_end=today + timedelta(days=end_offset) if end_offset is not None else None,
        description=description,
        countries=countries or [],
        status=status,
    )


class SeminarsListPosterLinkTests(TestCase):
    def test_card_links_poster_name_to_profile(self):
        poster = CustomUser.objects.create_user(
            email="visitposter@example.com", password="x", first_name="Val",
            last_name="Visitor", role=CustomUser.Role.RESEARCHER, is_active=True,
        )
        visit = make_seminar()
        visit.posted_by = poster
        visit.save()
        response = self.client.get(reverse("seminars-list"))
        self.assertContains(response, "Posted by")
        self.assertContains(
            response, f'href="{reverse("profile", args=[poster.pk])}"')


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

    def test_pending_visits_hidden(self):
        approved = make_seminar(visitor_name="Approved", start_offset=5)
        pending = make_seminar(visitor_name="Pending", start_offset=5, status="pending")
        response = self.client.get(reverse("seminars-list"))
        self.assertIn(approved, response.context["seminars"])
        self.assertNotIn(pending, response.context["seminars"])

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


class SeminarDetailViewTests(TestCase):
    def test_detail_renders(self):
        seminar = make_seminar()
        response = self.client.get(reverse("seminar-detail", kwargs={"pk": seminar.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "seminars/seminar_detail.html")

    def test_pending_visit_hidden_from_anonymous(self):
        seminar = make_seminar(status="pending")
        response = self.client.get(reverse("seminar-detail", kwargs={"pk": seminar.pk}))
        self.assertEqual(response.status_code, 404)

    def test_owner_can_view_pending_visit(self):
        owner = CustomUser.objects.create_user(
            email="owner@example.com", password="pw12345",
            first_name="Own", last_name="Er", is_active=True,
        )
        seminar = make_seminar(status="pending")
        seminar.posted_by = owner
        seminar.save()
        self.client.force_login(owner)
        response = self.client.get(reverse("seminar-detail", kwargs={"pk": seminar.pk}))
        self.assertEqual(response.status_code, 200)


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

    def _university(self):
        return University.objects.create(name="Cornell University", country_code="US")

    def _post_data(self, university, **overrides):
        data = {
            "country_code": "US",
            "university": university.pk,
            "visit_type": "open",
            "visit_start": timezone.localdate().isoformat(),
            "visit_end": "",
            "description": "A planned visit.",
        }
        data.update(overrides)
        return data

    def test_authenticated_user_can_create(self):
        self.client.force_login(self.user)
        university = self._university()
        response = self.client.post(
            reverse("seminar-create"), self._post_data(university))
        self.assertEqual(Seminar.objects.count(), 1)
        seminar = Seminar.objects.get()
        self.assertEqual(seminar.posted_by, self.user)
        self.assertEqual(seminar.countries, ["US"])
        self.assertEqual(seminar.visit_type, "open")
        self.assertEqual(seminar.status, "pending")
        self.assertRedirects(response, reverse("seminars-list"))

    def test_visitor_name_and_email_come_from_the_account(self):
        self.client.force_login(self.user)
        university = self._university()
        self.client.post(reverse("seminar-create"), self._post_data(
            university, visitor_name="Someone Else",
            visitor_email="attacker@example.com"))
        seminar = Seminar.objects.get()
        self.assertEqual(seminar.visitor_name, self.user.get_full_name())
        self.assertEqual(seminar.visitor_email, self.user.email)

    def test_create_allows_blank_description(self):
        self.client.force_login(self.user)
        university = self._university()
        response = self.client.post(
            reverse("seminar-create"), self._post_data(university, description=""))
        self.assertEqual(Seminar.objects.count(), 1)
        self.assertEqual(Seminar.objects.get().description, "")
        self.assertRedirects(response, reverse("seminars-list"))

    def test_visit_type_is_required(self):
        self.client.force_login(self.user)
        university = self._university()
        data = self._post_data(university)
        data.pop("visit_type")
        response = self.client.post(reverse("seminar-create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Seminar.objects.count(), 0)
        self.assertIn("visit_type", response.context["form"].errors)

    def test_university_is_now_required(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("seminar-create"), {
            "country_code": "US",
            "visit_type": "open",
            "visit_start": timezone.localdate().isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Seminar.objects.count(), 0)
        self.assertIn("university", response.context["form"].errors)


class VisitTypeFilterTests(TestCase):
    def test_facet_filters_by_visit_type(self):
        open_visit = make_seminar(visitor_name="Open One", start_offset=3)
        open_visit.visit_type = "open"
        open_visit.save()
        long_visit = make_seminar(visitor_name="Long One", start_offset=4)
        long_visit.visit_type = "long_term"
        long_visit.save()

        response = self.client.get(reverse("seminars-list"), {"visit_type": "open"})
        self.assertIn(open_visit, response.context["seminars"])
        self.assertNotIn(long_visit, response.context["seminars"])

    def test_unknown_visit_type_is_ignored(self):
        visit = make_seminar(start_offset=3)
        response = self.client.get(reverse("seminars-list"), {"visit_type": "bogus"})
        self.assertIn(visit, response.context["seminars"])


class VisitsUrlRedirectTests(TestCase):
    def test_seminars_root_redirects_to_visits(self):
        response = self.client.get("/seminars/")
        self.assertRedirects(response, "/visits/", status_code=302)

    def test_seminars_redirect_preserves_query_string(self):
        response = self.client.get("/seminars/?q=labor")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/visits/?q=labor")


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

    def test_live_fallback_fetches_over_https(self):
        with patch("seminars.views.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = OSError("blocked")
            self.client.get(reverse("seminar-universities"), {"country": "US"})

        called_url = mock_urlopen.call_args[0][0]
        self.assertTrue(called_url.startswith("https://"))


class SeminarDeleteViewTests(TestCase):
    def setUp(self):
        self.owner = CustomUser.objects.create_user(
            email="visitowner@example.com", password="pass12345",
            first_name="Visit", last_name="Owner", is_active=True,
        )
        self.other = CustomUser.objects.create_user(
            email="visitstranger@example.com", password="pass12345",
            first_name="No", last_name="One", is_active=True,
        )
        self.visit = make_seminar()
        self.visit.posted_by = self.owner
        self.visit.save()

    def test_non_owner_gets_404(self):
        self.client.force_login(self.other)
        response = self.client.post(reverse("visit-delete", args=[self.visit.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Seminar.objects.filter(pk=self.visit.pk).exists())

    def test_owner_can_delete(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("visit-delete", args=[self.visit.pk]))
        self.assertRedirects(response, reverse("seminars-list"))
        self.assertFalse(Seminar.objects.filter(pk=self.visit.pk).exists())
