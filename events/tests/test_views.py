from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from events.models import Event


def make_user(email="host@example.com"):
    return CustomUser.objects.create_user(
        email=email, password="pass12345",
        first_name="Host", last_name="User", is_active=True,
    )


def make_event(title="Event", offset_days=1, status="approved", **overrides):
    fields = dict(
        title=title,
        description="Description.",
        date=timezone.now() + timedelta(days=offset_days),
        location="Ithaca",
        status=status,
    )
    fields.update(overrides)
    return Event.objects.create(**fields)


class EventsListViewTests(TestCase):
    def test_only_approved_events_are_listed(self):
        approved = make_event(title="Approved", status="approved")
        pending = make_event(title="Pending", status="pending")
        response = self.client.get(reverse("events-list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(approved, response.context["events"])
        self.assertNotIn(pending, response.context["events"])

    def test_search_query_filters_by_title(self):
        match = make_event(title="Labor Economics Workshop")
        other = make_event(title="Unrelated Meetup")
        response = self.client.get(reverse("events-list"), {"q": "Labor"})
        self.assertIn(match, response.context["events"])
        self.assertNotIn(other, response.context["events"])

    def test_category_filter(self):
        conf = make_event(title="Conf", category="conference")
        work = make_event(title="Work", category="workshop")
        response = self.client.get(reverse("events-list"), {"category": "conference"})
        self.assertIn(conf, response.context["events"])
        self.assertNotIn(work, response.context["events"])

    def test_end_date_range_filter(self):
        soon = make_event(title="Soon", offset_days=1)
        far = make_event(title="Far", offset_days=40)
        end = timezone.now() + timedelta(days=5)
        response = self.client.get(
            reverse("events-list"),
            {"end_date": end.strftime("%Y-%m-%d")})
        self.assertIn(soon, response.context["events"])
        self.assertNotIn(far, response.context["events"])

    def test_sort_by_deadline_excludes_events_without_deadline(self):
        with_deadline = make_event(
            title="Has Deadline",
            deadline=timezone.now() + timedelta(days=3))
        without_deadline = make_event(title="No Deadline")
        response = self.client.get(reverse("events-list"), {"sort": "deadline"})
        self.assertIn(with_deadline, response.context["events"])
        self.assertNotIn(without_deadline, response.context["events"])


class EventsDetailViewTests(TestCase):
    def test_approved_event_is_visible(self):
        event = make_event(status="approved")
        response = self.client.get(
            reverse("event-detail", kwargs={"pk": event.pk}))
        self.assertEqual(response.status_code, 200)

    def test_pending_event_hidden_from_anonymous(self):
        event = make_event(status="pending")
        response = self.client.get(
            reverse("event-detail", kwargs={"pk": event.pk}))
        self.assertEqual(response.status_code, 404)

    def test_pending_event_visible_to_host(self):
        host = make_user()
        event = make_event(status="pending", host=host)
        self.client.force_login(host)
        response = self.client.get(
            reverse("event-detail", kwargs={"pk": event.pk}))
        self.assertEqual(response.status_code, 200)


class EventCreateViewTests(TestCase):
    def test_get_requires_login(self):
        response = self.client.get(reverse("event-create"))
        self.assertEqual(response.status_code, 302)

    def test_get_authenticated_renders(self):
        self.client.force_login(make_user())
        response = self.client.get(reverse("event-create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/event_form.html")

    def test_post_creates_pending_event_hosted_by_user(self):
        user = make_user()
        self.client.force_login(user)
        response = self.client.post(reverse("event-create"), {
            "title": "New Event",
            "description": "desc",
            "date": "2025-06-01",
            "location": "Ithaca",
            "category": "conference",
        })
        self.assertRedirects(response, reverse("events-list"))
        event = Event.objects.get(title="New Event")
        self.assertEqual(event.host, user)
        self.assertEqual(event.status, "pending")
