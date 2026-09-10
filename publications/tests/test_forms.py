from django.test import TestCase

from publications.forms import PublicationForm


def valid_form_data(**overrides):
    data = {
        "title": "A Study",
        "abstract": "Abstract text.",
        "country_code": "US",
        "is_job_market": True,
        "authors_input": '[{"value":"Jane Doe"}]',
        "topics_input": '[{"value":"Labor Supply"}]',
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

    def test_topics_are_stored_as_a_list(self):
        form = PublicationForm(data=valid_form_data(
            topics_input='[{"value":"Labor Supply"},{"value":"Migration"}]'))
        self.assertTrue(form.is_valid(), form.errors)
        publication = form.save()
        publication.topic = form.cleaned_data["topics_input"]
        self.assertEqual(publication.topic, ["Labor Supply", "Migration"])

    def test_off_whitelist_topic_is_rejected(self):
        form = PublicationForm(data=valid_form_data(
            topics_input='[{"value":"Not A Real Topic"}]'))
        self.assertFalse(form.is_valid())
        self.assertIn("topics_input", form.errors)

    def test_empty_topics_are_rejected(self):
        form = PublicationForm(data=valid_form_data(topics_input="[]"))
        self.assertFalse(form.is_valid())
        self.assertIn("topics_input", form.errors)

    def test_topic_casing_is_normalised_to_the_vocabulary(self):
        form = PublicationForm(data=valid_form_data(
            topics_input='[{"value":"labor supply"}]'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["topics_input"], ["Labor Supply"])

    def test_is_job_market_is_optional(self):
        data = valid_form_data()
        del data["is_job_market"]
        form = PublicationForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        publication = form.save()
        self.assertFalse(publication.is_job_market)

    def test_country_accepts_the_multinational_sentinel(self):
        form = PublicationForm(data=valid_form_data(country_code="MULTI"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().country_code, "MULTI")

    def test_country_rejects_an_unknown_code(self):
        form = PublicationForm(data=valid_form_data(country_code="ZZ"))
        self.assertFalse(form.is_valid())
        self.assertIn("country_code", form.errors)
