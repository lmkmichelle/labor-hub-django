from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from seminars.models import Seminar


def make_seminar(title="Seminar", offset_days=1, location="Ithaca",
                 description="Details."):
    return Seminar.objects.create(
        title=title,
        date=timezone.now() + timedelta(days=offset_days),
        location=location,
        description=description,
    )


class SeminarsListViewTests(TestCase):
    def test_list_renders(self):
        response = self.client.get(reverse("seminars-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "seminars/seminars_list.html")

    def test_search_filters_by_title(self):
        match = make_seminar(title="Labor Sabbatical")
        other = make_seminar(title="Unrelated")
        response = self.client.get(reverse("seminars-list"), {"q": "Labor"})
        self.assertIn(match, response.context["seminars"])
        self.assertNotIn(other, response.context["seminars"])

    def test_upcoming_filter(self):
        upcoming = make_seminar(title="Future", offset_days=5)
        past = make_seminar(title="Past", offset_days=-5)
        response = self.client.get(reverse("seminars-list"), {"filter": "upcoming"})
        self.assertIn(upcoming, response.context["seminars"])
        self.assertNotIn(past, response.context["seminars"])

    def test_past_filter(self):
        upcoming = make_seminar(title="Future", offset_days=5)
        past = make_seminar(title="Past", offset_days=-5)
        response = self.client.get(reverse("seminars-list"), {"filter": "past"})
        self.assertIn(past, response.context["seminars"])
        self.assertNotIn(upcoming, response.context["seminars"])

    def test_ordering_newest_first(self):
        older = make_seminar(title="Older", offset_days=1)
        newer = make_seminar(title="Newer", offset_days=10)
        response = self.client.get(reverse("seminars-list"))
        seminars = list(response.context["seminars"])
        self.assertEqual(seminars.index(newer), 0)
        self.assertLess(seminars.index(newer), seminars.index(older))

    def test_pagination_limits_to_ten(self):
        for i in range(11):
            make_seminar(title=f"Seminar {i}", offset_days=i + 1)
        response = self.client.get(reverse("seminars-list"))
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["seminars"]), 10)
