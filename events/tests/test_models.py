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


class EventLocationCompositionTests(TestCase):
    def test_save_composes_location_from_structured_fields(self):
        event = make_event(
            location="", country_code="US", city="Ithaca", venue="ILR")
        self.assertEqual(event.location, "ILR, Ithaca, United States")

    def test_save_omits_blank_venue(self):
        event = make_event(location="", country_code="US", city="Ithaca")
        self.assertEqual(event.location, "Ithaca, United States")

    def test_recompose_on_a_later_save(self):
        event = make_event(location="", country_code="US", city="Ithaca")
        event.city = "New York"
        event.save()
        self.assertEqual(event.location, "New York, United States")

    def test_legacy_free_text_location_survives_when_structured_fields_are_blank(self):
        # A pre-picker event has hand-typed text and no country_code/city --
        # re-saving it (e.g. an unrelated admin edit) must not wipe it out.
        event = make_event(location="Somewhere, TBD")
        event.admin_notes = "reviewed"
        event.save()
        self.assertEqual(event.location, "Somewhere, TBD")
