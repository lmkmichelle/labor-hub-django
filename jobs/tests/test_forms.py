from django.test import TestCase

from jobs.forms import JobForm


def job_form_data(**overrides):
    data = {
        "title": "Postdoc",
        "country_code": "US",
        "description": "Details.",
        "url": "https://example.com",
        "deadline": "2030-01-01",
        "categories": ["postdoc"],
    }
    data.update(overrides)
    return data


class JobFormTests(TestCase):
    def _data(self, **overrides):
        return job_form_data(**overrides)

    def test_valid_form_saves_country_as_list(self):
        form = JobForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)
        job = form.save()
        self.assertEqual(job.countries, ["US"])

    def test_saves_categories(self):
        form = JobForm(data=self._data(categories=["predoc", "postdoc"]))
        self.assertTrue(form.is_valid(), form.errors)
        job = form.save()
        self.assertEqual(sorted(job.categories), ["postdoc", "predoc"])

    def test_categories_required(self):
        form = JobForm(data=self._data(categories=[]))
        self.assertFalse(form.is_valid())
        self.assertIn("categories", form.errors)

    def test_missing_required_fields_invalid(self):
        form = JobForm(data=self._data(title="", url=""))
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)
        self.assertIn("url", form.errors)

    def test_country_required(self):
        form = JobForm(data=self._data(country_code=""))
        self.assertFalse(form.is_valid())
        self.assertIn("country_code", form.errors)


class JobFormPayEmployerTests(TestCase):
    def test_pay_and_employer_are_optional(self):
        form = JobForm(data=job_form_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_pay_and_employer_round_trip(self):
        form = JobForm(data=job_form_data(
            employer="Cornell ILR", pay="$70,000-85,000 / year"))
        self.assertTrue(form.is_valid(), form.errors)
        job = form.save(commit=False)
        self.assertEqual(job.employer, "Cornell ILR")
        self.assertEqual(job.pay, "$70,000-85,000 / year")
