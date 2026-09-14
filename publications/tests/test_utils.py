import json

from django.test import RequestFactory, TestCase

from accounts.models import CustomUser
from publications.forms import PublicationForm
from publications.models import Author, Publication
from publications.utils import (
    handle_authors,
    handle_keywords,
    process_publication_form,
)


class HandleKeywordsTests(TestCase):
    def test_returns_plain_string_list(self):
        raw = json.dumps([{"value": "economics"}, {"value": "labor"}])
        self.assertEqual(handle_keywords(raw), ["economics", "labor"])

    def test_accepts_plain_strings(self):
        raw = json.dumps(["economics", "labor"])
        self.assertEqual(handle_keywords(raw), ["economics", "labor"])

    def test_skips_blank_entries(self):
        raw = json.dumps([{"value": "economics"}, {"value": "  "}, ""])
        self.assertEqual(handle_keywords(raw), ["economics"])

    def test_empty_list(self):
        self.assertEqual(handle_keywords("[]"), [])


class HandleAuthorsTests(TestCase):
    def test_matches_user_by_id(self):
        user = CustomUser.objects.create_user(
            email="a@example.com", password="pass12345",
            first_name="Jane", last_name="Doe", is_active=True,
        )
        raw = json.dumps([{"value": "Jane Doe", "id": str(user.id)}])
        authors = handle_authors(raw)
        self.assertEqual(len(authors), 1)
        self.assertEqual(authors[0].user, user)

    def test_matches_user_by_name_when_no_id(self):
        user = CustomUser.objects.create_user(
            email="b@example.com", password="pass12345",
            first_name="John", last_name="Smith", is_active=True,
        )
        raw = json.dumps([{"value": "john smith"}])
        authors = handle_authors(raw)
        self.assertEqual(authors[0].user, user)

    def test_creates_anonymous_author_when_no_match(self):
        raw = json.dumps([{"value": "Unknown Person"}])
        authors = handle_authors(raw)
        self.assertEqual(len(authors), 1)
        self.assertIsNone(authors[0].user)
        self.assertEqual(authors[0].name, "Unknown Person")
        self.assertTrue(Author.objects.filter(name="Unknown Person").exists())


class ProcessPublicationFormTests(TestCase):
    def test_topic_comes_from_cleaned_data_not_raw_post(self):
        data = {
            "title": "Study", "abstract": "a", "country_code": "US",
            "authors_input": '[{"value":"Jane Doe"}]',
            "topics_input": '[{"value":"labor supply"}]',
        }
        form = PublicationForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        request = RequestFactory().post("/publications/submit/", data)
        request.user = CustomUser.objects.create_user(
            email="submitter@example.com", password="pass12345",
            first_name="Sub", last_name="Mitter", is_active=True,
        )
        publication = process_publication_form(request, form)
        # Canonical casing from clean_topics_input, stored as a list.
        self.assertEqual(publication.topic, ["Labor Supply"])
        self.assertEqual(
            Publication.objects.get(pk=publication.pk).authors.count(), 1)

    def test_editing_an_approved_paper_rebuilds_its_cover(self):
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PyPDF2 import PdfReader
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 700, "body")
        c.showPage()
        c.save()

        submitter = CustomUser.objects.create_user(
            email="approved-author@example.com", password="pass12345",
            first_name="App", last_name="Roved", is_active=True,
        )
        publication = Publication.objects.create(title="Old Title", abstract="a")
        publication.pdf_original.save(
            "o.pdf", SimpleUploadedFile("o.pdf", buf.getvalue()), save=True,
        )
        publication.discussion_paper_number = 5
        publication.save(update_fields=["discussion_paper_number"])

        data = {
            "title": "New Title", "abstract": "a", "country_code": "US",
            "authors_input": '[{"value":"App Roved"}]',
            "topics_input": '[{"value":"labor supply"}]',
        }
        form = PublicationForm(data=data, instance=publication)
        self.assertTrue(form.is_valid(), form.errors)
        request = RequestFactory().post("/publications/1/edit/", data)
        request.user = submitter

        process_publication_form(request, form)
        publication.refresh_from_db()
        with publication.pdf.open('rb') as f:
            reader = PdfReader(f)
            self.assertEqual(len(reader.pages), 2)
            self.assertIn("NEW TITLE", reader.pages[0].extract_text())
