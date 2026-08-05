from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from jobs.models import COUNTRY_MAP, RANK_MAP, Job


class JobModelTests(TestCase):
    def _job(self, **overrides):
        data = {
            "title": "Postdoc",
            "description": "Details.",
            "url": "https://example.com",
            "deadline": date(2030, 1, 1),
        }
        data.update(overrides)
        return Job.objects.create(**data)

    def test_str_is_title(self):
        self.assertEqual(str(self._job(title="Postdoc")), "Postdoc")

    def test_get_absolute_url(self):
        job = self._job()
        self.assertEqual(
            job.get_absolute_url(),
            reverse("job-detail", kwargs={"pk": job.pk}),
        )

    def test_country_labels_maps_codes(self):
        job = self._job(countries=["US"])
        self.assertEqual(job.country_labels(), [COUNTRY_MAP.get("US", "US")])

    def test_category_labels_maps_codes(self):
        job = self._job(categories=["assistant_professor", "predoc"])
        self.assertEqual(
            job.category_labels(),
            [RANK_MAP["assistant_professor"], RANK_MAP["predoc"]],
        )

    def test_new_job_defaults_to_pending(self):
        self.assertEqual(self._job().status, "pending")

    def test_approve_sets_status_and_reviewer(self):
        admin = CustomUser.objects.create_user(
            email="admin@example.com", password="pw12345",
            first_name="Ad", last_name="Min", is_active=True, is_staff=True,
        )
        job = self._job()
        job.approve(admin)
        self.assertEqual(job.status, "approved")
        self.assertEqual(job.reviewed_by, admin)
        self.assertIsNotNone(job.reviewed_at)

    def test_reject_sets_status(self):
        job = self._job()
        job.reject()
        self.assertEqual(job.status, "rejected")

    def test_cannot_approve_already_reviewed(self):
        job = self._job(status="approved")
        with self.assertRaises(ValueError):
            job.approve()
