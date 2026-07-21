from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from seminars.models import COUNTRY_MAP, Seminar, University


class SeminarModelTests(TestCase):
    def test_str_includes_visitor_university_and_start(self):
        seminar = Seminar.objects.create(
            visitor_name="Dr. Ada Lovelace",
            university_name="Cornell University",
            visit_start=date(2030, 5, 1),
        )
        self.assertEqual(
            str(seminar),
            "Dr. Ada Lovelace visiting Cornell University (2030-05-01)",
        )

    def test_get_university_display_prefers_related_university(self):
        university = University.objects.create(name="MIT", country_code="US")
        seminar = Seminar.objects.create(
            visitor_name="V", university=university, university_name="Ignored",
            visit_start=date(2030, 1, 1),
        )
        self.assertEqual(seminar.get_university_display(), "MIT")

    def test_get_university_display_falls_back_to_name_then_tba(self):
        with_name = Seminar.objects.create(
            visitor_name="V", university_name="Freetext U", visit_start=date(2030, 1, 1),
        )
        self.assertEqual(with_name.get_university_display(), "Freetext U")
        self.assertEqual(Seminar(visitor_name="V").get_university_display(), "University TBA")

    def test_country_labels_maps_codes(self):
        seminar = Seminar.objects.create(
            visitor_name="V", university_name="U", visit_start=date(2030, 1, 1),
            countries=["US"],
        )
        self.assertEqual(seminar.country_labels(), [COUNTRY_MAP.get("US", "US")])

    def test_get_absolute_url(self):
        seminar = Seminar.objects.create(
            visitor_name="V", university_name="U", visit_start=date(2030, 1, 1),
        )
        self.assertEqual(
            seminar.get_absolute_url(),
            reverse("seminar-detail", kwargs={"pk": seminar.pk}),
        )

    def test_clean_rejects_end_before_start(self):
        seminar = Seminar(
            visitor_name="V", university_name="U",
            visit_start=date(2030, 5, 10), visit_end=date(2030, 5, 1),
        )
        with self.assertRaises(ValidationError):
            seminar.clean()

    def test_clean_requires_a_university(self):
        seminar = Seminar(visitor_name="V", visit_start=date(2030, 5, 1))
        with self.assertRaises(ValidationError):
            seminar.clean()
