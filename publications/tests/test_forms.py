from django.test import TestCase

from publications.forms import PublicationForm


def valid_form_data(**overrides):
    data = {
        "title": "A Study",
        "date": "2025-06-01",
        "abstract": "Abstract text.",
        "country_code": "US",
        "study_url": "https://example.com/study",
        "is_job_market": True,
        "authors_input": '[{"value":"Jane Doe"}]',
        "topic_input": "Labor",
        "keywords_input": '[{"value":"economics"}]',
    }
    data.update(overrides)
    return data


class PublicationFormTests(TestCase):
    def test_valid_without_pdf_saves(self):
        form = PublicationForm(data=valid_form_data())
        self.assertTrue(form.is_valid(), form.errors)
        publication = form.save()
        self.assertIsNotNone(publication.pk)
        self.assertFalse(publication.pdf)

    def test_missing_required_author_field_is_invalid(self):
        data = valid_form_data()
        del data["authors_input"]
        form = PublicationForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("authors_input", form.errors)

    def test_is_job_market_is_optional(self):
        data = valid_form_data()
        del data["is_job_market"]
        form = PublicationForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        publication = form.save()
        self.assertFalse(publication.is_job_market)
