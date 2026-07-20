from datetime import time as dtime, timedelta

from django.test import TestCase
from django.utils import timezone

from events.forms import EventForm
from events.models import Event


def form_data(**overrides):
    data = {
        "title": "My Event",
        "description": "Some description.",
        "date": "2025-06-01",
        "location": "Ithaca",
        "category": "conference",
    }
    data.update(overrides)
    return data


class EventFormDeadlineTests(TestCase):
    def test_combines_deadline_date_and_time(self):
        form = EventForm(data=form_data(
            deadline_date="2025-05-01", deadline_time="14:30"))
        self.assertTrue(form.is_valid(), form.errors)
        deadline = form.cleaned_data["deadline"]
        self.assertIsNotNone(deadline)
        self.assertTrue(timezone.is_aware(deadline))
        self.assertEqual((deadline.hour, deadline.minute), (14, 30))

    def test_defaults_deadline_time_to_end_of_day(self):
        form = EventForm(data=form_data(deadline_date="2025-05-01"))
        self.assertTrue(form.is_valid(), form.errors)
        deadline = form.cleaned_data["deadline"]
        self.assertEqual((deadline.hour, deadline.minute), (23, 59))

    def test_no_deadline_date_yields_none(self):
        form = EventForm(data=form_data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["deadline"])

    def test_prefills_split_fields_when_editing(self):
        deadline = timezone.make_aware(
            timezone.datetime(2025, 5, 1, 9, 15))
        event = Event.objects.create(
            title="E", description="d",
            date=timezone.now() + timedelta(days=1),
            location="Ithaca", deadline=deadline,
        )
        form = EventForm(instance=event)
        self.assertEqual(form.fields["deadline_date"].initial, deadline.date())
        self.assertEqual(form.fields["deadline_time"].initial, "09:15")
