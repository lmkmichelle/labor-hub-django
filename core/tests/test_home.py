from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from events.models import Event
from jobs.models import Job
from publications.models import Publication


def member(email, role=CustomUser.Role.RESEARCHER, days_ago=0):
    user = CustomUser.objects.create_user(
        email=email, password="x", first_name=email.split("@")[0].title(),
        last_name="Test", role=role, is_active=True)
    CustomUser.objects.filter(pk=user.pk).update(
        date_joined=timezone.now() - timedelta(days=days_ago))
    return user


class HomeHeroTests(TestCase):
    def _event(self, title, days, category="workshop"):
        return Event.objects.create(
            title=title, description="Long description text", category=category,
            date=timezone.now() + timedelta(days=days), location="Essen", status="approved")

    def test_hero_shows_only_the_three_newest_announcements_compactly(self):
        for i, title in enumerate(("Oldest", "Older", "Newer", "Newest")):
            event = self._event(title, 3)
            Event.objects.filter(pk=event.pk).update(
                created_at=timezone.now() - timedelta(days=10 - i))
        page = self.client.get(reverse("home"))
        titles = [e["obj"].title for e in page.context["recent_announcements"]]
        self.assertEqual(titles, ["Newest", "Newer", "Older"])
        self.assertContains(page, "New announcements")
        self.assertNotContains(page, "Oldest")
        self.assertNotContains(page, "New researchers")

    def test_hero_cards_keep_their_colours_but_drop_the_body(self):
        job = Job.objects.create(
            title="Postdoc", description="A long job description", url="https://example.com",
            deadline=timezone.localdate() + timedelta(days=30), status="approved")
        self._event("Conf", 3, category="conference")
        html = self.client.get(reverse("home")).content.decode()
        self.assertIn("theme-teal", html)
        self.assertIn("theme-orange", html)
        self.assertNotIn("A long job description", html)
        full = self.client.get(reverse("announcements")).content.decode()
        self.assertIn("A long job description", full)

    def test_has_all_six_links(self):
        page = self.client.get(reverse("home"))
        for name in ("publications", "scholars", "map", "special-issues-list",
                     "seminars-list", "jobs-list", "announcements"):
            self.assertContains(page, f'href="{reverse(name)}"')
        for label in ("Special issues", "Long-distance visits", "New jobs"):
            self.assertContains(page, label)


class HomePapersTests(TestCase):
    def test_six_newest_papers_with_both_series_colours_and_no_tabs(self):
        Publication.objects.create(
            title="Market Paper", abstract="a", status="approved",
            is_job_market=True, job_market_paper_number=1)
        for n in range(2, 9):
            Publication.objects.create(
                title=f"Paper {n}", abstract="a", status="approved", discussion_paper_number=n)
        page = self.client.get(reverse("home"))
        self.assertEqual(len(page.context["recent_papers"]), 6)
        html = page.content.decode()
        self.assertIn("Recent Papers", html)
        self.assertNotIn('role="tablist"', html)
        Publication.objects.filter(title="Market Paper").update(
            applied_at=timezone.now() + timedelta(days=1))
        html = self.client.get(reverse("home")).content.decode()
        self.assertIn("Job Market Paper No. J1", html)
        self.assertIn("jm-theme", html)
        self.assertIn("Discussion Paper No.", html)

    def test_layout_switch_is_gone(self):
        page = self.client.get(reverse("home"), {"layout": "split"})
        self.assertNotIn("home_layout", page.context)


class AnnouncementColourTests(TestCase):
    """Conferences/workshops are blue and special issues purple, like green job market papers."""

    def _event(self, category):
        return Event.objects.create(
            title=f"A {category}", description="d", category=category,
            date=timezone.now() + timedelta(days=3), location="Essen", status="approved")

    def test_workshops_are_blue_conferences_orange_others_red(self):
        for category, scope in (("conference", "theme-orange"), ("workshop", "theme-blue"),
                                ("schools", None), ("other", None)):
            event = self._event(category)
            html = self.client.get(reverse("announcements")).content.decode()
            html = html[html.index("</nav>", html.index("Announcement types")):]  # past the filter tabs, which carry theme classes too
            card = html[max(0, html.index(event.title) - 600):html.index(event.title)]
            for name in ("theme-blue", "theme-orange"):
                self.assertEqual(name in card, name == scope, (category, name))

    def test_event_detail_page_carries_the_scope(self):
        page = self.client.get(reverse("event-detail", args=[self._event("workshop").pk]))
        self.assertContains(page, "theme-blue")
        page = self.client.get(reverse("event-detail", args=[self._event("conference").pk]))
        self.assertContains(page, "theme-orange")
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

    def test_job_card_and_detail_are_teal_with_a_label(self):
        job = Job.objects.create(
            title="Research Data Analyst", description="d", url="https://example.com",
            deadline=timezone.localdate() + timedelta(days=30), status="approved")
        feed = self.client.get(reverse("announcements"))
        self.assertContains(feed, "theme-teal")
        self.assertContains(feed, '<span class="pill-accent">Job</span>', html=True)
        detail = self.client.get(reverse("job-detail", args=[job.pk]))
        self.assertContains(detail, "theme-teal")
        self.assertContains(detail, "Job</span>")


class AnnouncementTabColourTests(TestCase):
    def test_active_tab_takes_its_types_colour_and_all_stays_red(self):
        for name, scope in (("jobs-list", "theme-teal"), ("events-list", "theme-blue"),
                            ("special-issues-list", "theme-purple")):
            html = self.client.get(reverse(name)).content.decode()
            active = [l for l in html.splitlines() if "announce-tab-active" in l]
            self.assertEqual(len(active), 1, name)
            self.assertIn(scope, active[0], name)
        feed = self.client.get(reverse("announcements")).content.decode()
        active = [l for l in feed.splitlines() if "announce-tab-active" in l][0]
        self.assertNotIn("theme-", active)
