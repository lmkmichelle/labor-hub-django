import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PyPDF2 import PdfReader
from reportlab.pdfgen import canvas

from accounts.models import CustomUser
from publications.forms import PublicationForm


def valid_form_data(**overrides):
    data = {
        "title": "A Study",
        "abstract": "Abstract text.",
        "country_code": "US",
        "is_job_market": "",
        "authors_input": '[{"value":"Jane Doe"}]',
        "topics_input": '[{"value":"Labor Supply"}]',
    }
    data.update(overrides)
    return data


def make_researcher(email="advisor@example.com"):
    return CustomUser.objects.create_user(
        email=email, password="pass12345", first_name="Ada", last_name="Visor",
        role=CustomUser.Role.RESEARCHER, is_active=True,
    )


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

    def test_job_market_paper_requires_an_advisor(self):
        form = PublicationForm(data=valid_form_data(is_job_market=True))
        self.assertFalse(form.is_valid())
        self.assertIn("jm_advisor", form.errors)

    def test_job_market_paper_with_a_researcher_advisor_is_valid(self):
        advisor = make_researcher()
        form = PublicationForm(data=valid_form_data(
            is_job_market=True, jm_advisor=advisor.pk))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().jm_advisor, advisor)

    def test_students_are_not_in_the_advisor_queryset(self):
        student = CustomUser.objects.create_user(
            email="student@example.com", password="pass12345",
            first_name="Sam", last_name="Student",
            role=CustomUser.Role.STUDENT, is_active=True,
        )
        self.assertNotIn(student, PublicationForm().fields["jm_advisor"].queryset)

    def test_advisor_is_discarded_when_box_unchecked(self):
        advisor = make_researcher()
        form = PublicationForm(data=valid_form_data(jm_advisor=advisor.pk))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["jm_advisor"])

    def test_country_accepts_the_multinational_sentinel(self):
        form = PublicationForm(data=valid_form_data(country_code="MULTI"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().country_code, "MULTI")

    def test_country_rejects_an_unknown_code(self):
        form = PublicationForm(data=valid_form_data(country_code="ZZ"))
        self.assertFalse(form.is_valid())
        self.assertIn("country_code", form.errors)

    def test_upload_is_stored_uncovered_on_both_pdf_fields(self):
        """The form itself no longer merges a cover in -- that only happens
        once the paper is approved and numbered (see Publication.approve)."""
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 700, "author's own text")
        c.showPage()
        c.save()
        upload = SimpleUploadedFile("paper.pdf", buf.getvalue(), content_type="application/pdf")

        form = PublicationForm(data=valid_form_data(), files={"pdf": upload})
        self.assertTrue(form.is_valid(), form.errors)
        publication = form.save()

        self.assertTrue(publication.pdf)
        self.assertTrue(publication.pdf_original)
        with publication.pdf.open('rb') as f:
            reader = PdfReader(f)
            self.assertEqual(len(reader.pages), 1)
            self.assertIn("author's own text", reader.pages[0].extract_text())
