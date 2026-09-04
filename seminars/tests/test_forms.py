from django.test import TestCase
from django.utils import timezone

from seminars.forms import SeminarForm
from seminars.models import University


def valid_data(**overrides):
    data = {
        "country_code": "US",
        "visitor_name": "Val Visitor",
        "visitor_email": "val@example.com",
        "visitor_affiliation": "",
        "visit_start": timezone.localdate().isoformat(),
        "visit_end": "",
        "description": "",
    }
    data.update(overrides)
    return data


class SeminarFormTests(TestCase):
    def setUp(self):
        self.university = University.objects.create(
            name="Cornell University", country_code="US")

    def test_valid_with_university(self):
        form = SeminarForm(data=valid_data(university=self.university.pk))
        self.assertTrue(form.is_valid(), form.errors)

    def test_university_is_required(self):
        form = SeminarForm(data=valid_data())
        self.assertFalse(form.is_valid())
        self.assertIn("university", form.errors)

    def test_university_name_is_no_longer_a_form_field(self):
        self.assertNotIn("university_name", SeminarForm().fields)
        # A posted university_name must not leak through onto the instance.
        form = SeminarForm(data=valid_data(
            university=self.university.pk, university_name="Sneaky University"))
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        self.assertNotEqual(instance.university_name, "Sneaky University")
