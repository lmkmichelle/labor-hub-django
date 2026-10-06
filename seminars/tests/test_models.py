from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from seminars.models import COUNTRY_MAP, Seminar, University


class UniversityFromWriteInTests(TestCase):
    def test_creates_a_write_in_university(self):
        university = University.from_write_in("Obscure College", "US")
        self.assertEqual(university.name, "Obscure College")
        self.assertEqual(university.country_code, "US")
        self.assertEqual(university.source, "write-in")

    def test_reuses_an_existing_name_case_insensitively(self):
        existing = University.objects.create(
            name="Existing College", country_code="US", source="import")
        university = University.from_write_in("existing college", "US")
        self.assertEqual(university.pk, existing.pk)
        self.assertEqual(University.objects.filter(name__iexact="existing college").count(), 1)

    def test_same_name_different_country_is_a_different_university(self):
        University.from_write_in("Shared Name", "US")
        university = University.from_write_in("Shared Name", "CA")
        self.assertEqual(university.country_code, "CA")
        self.assertEqual(University.objects.filter(name="Shared Name").count(), 2)

    def test_returns_none_without_a_name(self):
        self.assertIsNone(University.from_write_in("", "US"))

    def test_returns_none_without_a_country(self):
        self.assertIsNone(University.from_write_in("Some College", ""))


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

    def test_new_seminar_defaults_to_pending(self):
        seminar = Seminar.objects.create(
            visitor_name="V", university_name="U", visit_start=date(2030, 1, 1),
        )
        self.assertEqual(seminar.status, "pending")

    def test_approve_and_reject_guard(self):
        seminar = Seminar.objects.create(
            visitor_name="V", university_name="U", visit_start=date(2030, 1, 1),
        )
        seminar.approve()
        self.assertEqual(seminar.status, "approved")
        with self.assertRaises(ValueError):
            seminar.reject()


class SeminarApprovePromotesWriteInTests(TestCase):
    def _pending(self, **fields):
        return Seminar.objects.create(
            visitor_name="V", status="pending", countries=["DE"], **fields)

    def test_approving_a_write_in_visit_creates_the_university(self):
        visit = self._pending(university_name="Brand New Institute")
        visit.approve()
        visit.refresh_from_db()
        self.assertEqual(visit.university.name, "Brand New Institute")
        self.assertEqual(visit.university.country_code, "DE")
        self.assertEqual(visit.university_name, "")

    def test_a_pending_visit_does_not_create_a_university(self):
        self._pending(university_name="Not Yet Institute")
        self.assertFalse(University.objects.filter(name="Not Yet Institute").exists())

    def test_a_picked_university_is_left_alone(self):
        university = University.objects.create(name="Picked U", country_code="DE")
        visit = self._pending(university=university, university_name="ignored")
        visit.approve()
        visit.refresh_from_db()
        self.assertEqual(visit.university, university)
        self.assertEqual(University.objects.count(), 1)

    def test_no_country_means_no_promotion(self):
        visit = Seminar.objects.create(
            visitor_name="V", status="pending", university_name="Nowhere U")
        visit.approve()
        visit.refresh_from_db()
        self.assertIsNone(visit.university)
        self.assertEqual(visit.university_name, "Nowhere U")


class UniversitySearchTests(TestCase):
    def setUp(self):
        from accounts.models import CustomUser
        self.user = CustomUser.objects.create_user(
            email="s@example.com", password="pass12345", is_active=True)
        self.client.force_login(self.user)

    def _search(self, q):
        return self.client.get(reverse("university-search"), {"q": q}).json()["universities"]

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("university-search"), {"q": "harv"})
        self.assertEqual(response.status_code, 302)

    def test_short_query_returns_nothing(self):
        University.objects.create(name="Harvard University", country_code="US")
        self.assertEqual(self._search("h"), [])

    def test_prefix_matches_come_before_infix(self):
        University.objects.create(name="Old Harvard Institute", country_code="US")
        University.objects.create(name="Harvard University", country_code="US")
        results = self._search("harv")
        self.assertEqual(
            [r["label"] for r in results],
            ["Harvard University, United States", "Old Harvard Institute, United States"])

    def test_results_are_capped(self):
        University.objects.bulk_create(
            University(name=f"Test University {i}", country_code="US") for i in range(40))
        self.assertEqual(len(self._search("test univ")), 20)
