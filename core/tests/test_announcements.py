from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from events.models import Event
from jobs.models import Job
from seminars.models import Seminar
from special_issues.models import SpecialIssue


def _stamp(model, obj, hours_ago):
    model.objects.filter(pk=obj.pk).update(
        created_at=timezone.now() - timedelta(hours=hours_ago)
    )


def make_job(title="Job", hours_ago=1, deadline_days=30, status="approved"):
    job = Job.objects.create(
        title=title, description="d", url="https://e.com", countries=["US"],
        deadline=timezone.localdate() + timedelta(days=deadline_days), status=status,
    )
    _stamp(Job, job, hours_ago)
    return job


def make_event(title="Event", hours_ago=1, date_days=10, status="approved"):
    event = Event.objects.create(
        title=title, description="d", location="NYC", status=status,
        date=timezone.now() + timedelta(days=date_days),
    )
    _stamp(Event, event, hours_ago)
    return event


def make_visit(name="Visitor", hours_ago=1, start_days=10, status="approved"):
    visit = Seminar.objects.create(
        visitor_name=name, visitor_email="v@e.com", university_name="Cornell",
        visit_start=timezone.localdate() + timedelta(days=start_days),
        countries=["US"], status=status,
    )
    _stamp(Seminar, visit, hours_ago)
    return visit


def make_issue(title="Issue", hours_ago=1, deadline_days=30, status="approved"):
    issue = SpecialIssue.objects.create(
        journal="J", title=title, description="d", status=status,
        submission_deadline=timezone.localdate() + timedelta(days=deadline_days),
    )
    _stamp(SpecialIssue, issue, hours_ago)
    return issue


class AnnouncementsFeedTests(TestCase):
    url = property(lambda self: reverse("announcements"))

    def test_merges_all_four_types_newest_first(self):
        make_job("Job A", hours_ago=4)
        make_event("Event B", hours_ago=3)
        make_issue("Issue C", hours_ago=2)
        make_visit("Visitor D", hours_ago=1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [e["kind"] for e in response.context["announcements"]],
            ["visit", "special_issue", "event", "job"],
        )
        for text in ("Job A", "Event B", "Issue C", "Visitor D"):
            self.assertContains(response, text)

    def test_hides_pending_and_already_over_items(self):
        make_job("Pending Job", status="pending")
        make_job("Old Job", deadline_days=-1)
        make_event("Old Event", date_days=-5)
        make_issue("Old Issue", deadline_days=-1)
        make_visit("Old Visitor", start_days=-5)
        make_job("Live Job")
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["announcements"]), 1)
        self.assertContains(response, "Live Job")

    def test_paginates_across_types(self):
        for i in range(7):
            make_job(f"J{i}", hours_ago=100 + i)
            make_event(f"E{i}", hours_ago=50 + i)
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["announcements"]), 10)
        self.assertTrue(response.context["is_paginated"])
        page2 = self.client.get(self.url, {"page": 2})
        self.assertEqual(len(page2.context["announcements"]), 4)

    def test_query_count_is_constant(self):
        # count + page of ids + one bulk load per type, however many rows exist.
        for i in range(3):
            make_job(f"J{i}")
            make_event(f"E{i}")
            make_issue(f"I{i}")
            make_visit(f"V{i}")
        with self.assertNumQueries(6):
            self.client.get(self.url)

    def test_empty_state(self):
        self.assertContains(self.client.get(self.url), "There are no announcements right now.")

    def test_type_tabs_link_to_each_list_page(self):
        response = self.client.get(self.url)
        for name in ("jobs-list", "events-list", "special-issues-list", "seminars-list"):
            self.assertContains(response, f'href="{reverse(name)}"')


class PostAnnouncementChooserTests(TestCase):
    url = property(lambda self: reverse("announcement-new"))

    def login(self, role):
        user = CustomUser.objects.create_user(
            email=f"{role}@example.com", password="x", first_name="A", last_name="B",
            role=role, is_active=True,
        )
        self.client.force_login(user)

    def test_requires_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_researcher_sees_special_issue_option(self):
        self.login(CustomUser.Role.RESEARCHER)
        response = self.client.get(self.url)
        self.assertContains(response, reverse("special-issue-create"))
        for name in ("job-create", "event-create", "seminar-create"):
            self.assertContains(response, reverse(name))

    def test_student_does_not_see_special_issue_option(self):
        self.login(CustomUser.Role.STUDENT)
        response = self.client.get(self.url)
        self.assertNotContains(response, reverse("special-issue-create"))
        self.assertContains(response, reverse("job-create"))


class NavSectionTests(TestCase):
    def test_announcements_highlighted_on_each_member_page(self):
        for name in ("announcements", "jobs-list", "events-list", "seminars-list", "special-issues-list"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.context["nav_section"], "announcements", name)

    def test_other_sections(self):
        self.assertEqual(self.client.get(reverse("publications")).context["nav_section"], "papers")
        self.assertEqual(self.client.get(reverse("scholars")).context["nav_section"], "scholars")


class TopNavTests(TestCase):
    def test_nav_lists_exactly_the_four_sections(self):
        response = self.client.get("/")
        nav = response.content.decode().split('id="navbar-cta"')[1].split("</ul>")[0]
        for label in ("Scholars", "Announcements", "Research Papers", "Contact Us"):
            self.assertIn(label, nav)
        for gone in ("World Map", "Discussion Papers", ">Home<", ">Events<", ">Jobs<"):
            self.assertNotIn(gone, nav)
        self.assertLess(nav.index("Scholars"), nav.index("Announcements"))
        self.assertLess(nav.index("Announcements"), nav.index("Research Papers"))
        self.assertLess(nav.index("Research Papers"), nav.index("Contact Us"))

    def test_user_menu_has_one_post_an_announcement_link(self):
        user = CustomUser.objects.create_user(
            email="m@example.com", password="x", first_name="M", last_name="N",
            role=CustomUser.Role.RESEARCHER, is_active=True,
        )
        self.client.force_login(user)
        html = self.client.get("/").content.decode()
        self.assertIn(reverse("announcement-new"), html)
        for old in (">Post a Job<", ">Post a Visit<", ">Post an Event<"):
            self.assertNotIn(old, html)
