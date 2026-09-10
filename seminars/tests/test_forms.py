from django.test import TestCase
from django.utils import timezone

from seminars.forms import SeminarForm
from seminars.models import University


def valid_data(**overrides):
    data = {
        "country_code": "US",
        "visit_type": "open",
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

    def test_visit_type_is_required(self):
        data = valid_data(university=self.university.pk)
        data.pop("visit_type")
        form = SeminarForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("visit_type", form.errors)

    def test_visitor_fields_are_no_longer_on_the_form(self):
        fields = SeminarForm().fields
        self.assertNotIn("visitor_name", fields)
        self.assertNotIn("visitor_email", fields)
        self.assertNotIn("visitor_affiliation", fields)

    def test_university_name_is_no_longer_a_form_field(self):
        self.assertNotIn("university_name", SeminarForm().fields)
        # A posted university_name must not leak through onto the instance.
        form = SeminarForm(data=valid_data(
            university=self.university.pk, university_name="Sneaky University"))
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        self.assertNotEqual(instance.university_name, "Sneaky University")
