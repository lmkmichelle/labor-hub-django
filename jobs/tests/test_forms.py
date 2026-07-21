from django.test import TestCase

from jobs.forms import JobForm


class JobFormTests(TestCase):
    def _data(self, **overrides):
        data = {
            "title": "Postdoc",
            "country_code": "US",
            "description": "Details.",
            "url": "https://example.com",
            "deadline": "2030-01-01",
            "is_for_graduate_students": "",
        }
        data.update(overrides)
        return data

    def test_valid_form_saves_country_as_list(self):
        form = JobForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)
        job = form.save()
        self.assertEqual(job.countries, ["US"])

    def test_missing_required_fields_invalid(self):
        form = JobForm(data=self._data(title="", url=""))
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)
        self.assertIn("url", form.errors)

    def test_country_required(self):
        form = JobForm(data=self._data(country_code=""))
        self.assertFalse(form.is_valid())
        self.assertIn("country_code", form.errors)
