from datetime import date

from django.test import TestCase
from django.urls import reverse

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
