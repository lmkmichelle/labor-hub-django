from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from events.models import Event


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


class EventModelTests(TestCase):
    def test_str_returns_title(self):
        event = make_event(title="Conference")
        self.assertEqual(str(event), "Conference")

    def test_is_upcoming_true_for_future(self):
        event = make_event(offset_days=5)
        self.assertTrue(event.is_upcoming)

    def test_is_upcoming_false_for_past(self):
        event = make_event(offset_days=-5)
        self.assertFalse(event.is_upcoming)

    def test_default_ordering_by_date(self):
        later = make_event(title="Later", offset_days=10)
        sooner = make_event(title="Sooner", offset_days=2)
        self.assertEqual(list(Event.objects.all()), [sooner, later])
