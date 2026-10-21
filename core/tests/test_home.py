from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from events.models import Event
from publications.models import Publication


def member(email, role=CustomUser.Role.RESEARCHER, days_ago=0):
    user = CustomUser.objects.create_user(
        email=email, password="x", first_name=email.split("@")[0].title(),
        last_name="Test", role=role, is_active=True)
    CustomUser.objects.filter(pk=user.pk).update(
        date_joined=timezone.now() - timedelta(days=days_ago))
    return user


class HomeHeroTests(TestCase):
    def test_lists_the_three_newest_members_students_included(self):
        member("oldest@example.com", days_ago=9)
        member("scholar@example.com", days_ago=3)
        member("student@example.com", CustomUser.Role.STUDENT, days_ago=2)
        member("newest@example.com", days_ago=1)
        page = self.client.get(reverse("home"))
        names = [u.first_name for u in page.context["new_researchers"]]
        self.assertEqual(names, ["Newest", "Student", "Scholar"])
        self.assertContains(page, "New researchers")

    def test_has_all_six_links(self):
        page = self.client.get(reverse("home"))
        for name in ("publications", "scholars", "map", "special-issues-list",
                     "seminars-list", "jobs-list"):
            self.assertContains(page, f'href="{reverse(name)}"')
        for label in ("Special issues", "Long-distance visits", "New jobs"):
            self.assertContains(page, label)


class HomeLayoutTests(TestCase):
    def setUp(self):
        Event.objects.create(
            title="Gender Workshop", description="d", category="workshop",
            date=timezone.now() + timedelta(days=3), location="Essen",
            status="approved")
        Publication.objects.create(
            title="Market Paper", abstract="a", status="approved",
            is_job_market=True, job_market_paper_number=1)

    def test_wide_is_the_default(self):
        page = self.client.get(reverse("home"))
        self.assertEqual(page.context["home_layout"], "wide")
        self.assertTemplateUsed(page, "partials/_home_wide.html")
        self.assertTemplateNotUsed(page, "partials/_home_split.html")

    def test_query_string_switches_layout(self):
        page = self.client.get(reverse("home"), {"layout": "split"})
        self.assertTemplateUsed(page, "partials/_home_split.html")
        self.assertTemplateNotUsed(page, "partials/_home_wide.html")

    @override_settings(HOME_LAYOUT="split")
    def test_setting_changes_the_default_and_query_still_wins(self):
        self.assertTemplateUsed(self.client.get(reverse("home")), "partials/_home_split.html")
        self.assertTemplateUsed(
            self.client.get(reverse("home"), {"layout": "wide"}), "partials/_home_wide.html")

    def test_unknown_layout_falls_back_to_the_default(self):
        page = self.client.get(reverse("home"), {"layout": "bogus"})
        self.assertEqual(page.context["home_layout"], "wide")

    def test_both_layouts_keep_the_job_market_colour_and_their_order(self):
        for layout in ("wide", "split"):
            html = self.client.get(reverse("home"), {"layout": layout}).content.decode()
            self.assertIn("Job Market Paper No. J1", html)
            self.assertIn("jm-theme", html)
            first, second = (("Recent Papers", "Recent Announcements") if layout == "wide"
                             else ("Recent Announcements", "Recent Papers"))
            self.assertLess(html.index(first), html.index(second))
            self.assertIn("Gender Workshop", html)


class AnnouncementColourTests(TestCase):
    """Conferences/workshops are blue and special issues purple, like green job market papers."""

    def _event(self, category):
        return Event.objects.create(
            title=f"A {category}", description="d", category=category,
            date=timezone.now() + timedelta(days=3), location="Essen", status="approved")

    def test_conference_and_workshop_cards_are_blue_others_are_not(self):
        for category, blue in (("conference", True), ("workshop", True),
                               ("schools", False), ("other", False)):
            event = self._event(category)
            html = self.client.get(reverse("announcements")).content.decode()
            card = html[html.index(event.title) - 600:html.index(event.title)]
            self.assertEqual("theme-blue" in card, blue, category)

    def test_event_detail_page_carries_the_scope(self):
        page = self.client.get(reverse("event-detail", args=[self._event("workshop").pk]))
        self.assertContains(page, "theme-blue")
        page = self.client.get(reverse("event-detail", args=[self._event("other").pk]))
        self.assertNotContains(page, "theme-blue")

    def test_special_issue_card_and_detail_are_purple_with_a_label(self):
        from special_issues.models import SpecialIssue
        issue = SpecialIssue.objects.create(
            title="Sports as Natural Experiments", journal="SJPE", description="d",
            submission_deadline=timezone.localdate() + timedelta(days=30), status="approved")
        feed = self.client.get(reverse("announcements"))
        self.assertContains(feed, "theme-purple")
        self.assertContains(feed, '<span class="pill-accent">Special Issue</span>', html=True)
        detail = self.client.get(reverse("special-issue-detail", args=[issue.pk]))
        self.assertContains(detail, "theme-purple")
        self.assertContains(detail, "Special Issue</span>")
