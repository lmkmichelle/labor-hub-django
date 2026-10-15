"""Replaced PDFs are deleted instead of piling up on the persistent disk."""
import io
import os
import shutil
import tempfile

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from reportlab.pdfgen import canvas

from accounts.models import CustomUser
from publications.forms import PublicationForm
from publications.models import Publication
from publications.utils import process_publication_form


def tiny_pdf(text="body"):
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer)
    page.drawString(100, 700, text)
    page.showPage()
    page.save()
    return buffer.getvalue()


def files_under(root, *parts):
    folder = os.path.join(root, *parts)
    return sorted(f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))) \
        if os.path.isdir(folder) else []


class MediaCleanupTestCase(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="laborhub-cleanup-")
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)

    def pending_paper(self, title="Old Title"):
        """A pending paper as the submit form leaves it: the author's file twice."""
        paper = Publication.objects.create(title=title, abstract="a", status="pending")
        paper.pdf_original.save("mine.pdf", ContentFile(tiny_pdf()), save=False)
        paper.pdf.save("mine.pdf", ContentFile(tiny_pdf()), save=True)
        return paper


class CoverReplacementTests(MediaCleanupTestCase):
    def test_approving_deletes_the_pending_copy_and_keeps_the_original(self):
        paper = self.pending_paper()
        pending_copy = paper.pdf.name
        paper.approve()
        paper.refresh_from_db()
        self.assertNotEqual(paper.pdf.name, pending_copy)
        self.assertFalse(paper.pdf.storage.exists(pending_copy))
        self.assertTrue(paper.pdf.storage.exists(paper.pdf_original.name))
        self.assertTrue(paper.pdf.storage.exists(paper.pdf.name))
        self.assertEqual(len(files_under(self.media, "publications", "pdf")), 1)

    def test_editing_an_approved_paper_replaces_its_cover_in_place(self):
        paper = self.pending_paper()
        paper.approve()
        for title in ("New Title", "New Title", "Another Title"):  # same name twice, then a new one
            paper.title = title
            paper.save()
            paper.rebuild_covered_pdf()
            paper.refresh_from_db()
            self.assertEqual(
                len(files_under(self.media, "publications", "pdf")), 1, title)
            self.assertTrue(paper.pdf.storage.exists(paper.pdf.name))
        self.assertEqual(len(files_under(self.media, "publications", "pdf", "original")), 1)

    def test_rebuild_without_saving_keeps_the_old_file(self):
        paper = self.pending_paper()
        paper.approve()
        before = paper.pdf.name
        paper.rebuild_covered_pdf(save=False)
        self.assertTrue(paper.pdf.storage.exists(before))

    def test_discard_file_never_deletes_a_file_the_paper_uses(self):
        paper = self.pending_paper()
        paper.discard_file(paper.pdf.name)
        paper.discard_file(paper.pdf_original.name)
        paper.discard_file("")
        paper.discard_file("publications/pdf/not-there.pdf")  # already gone: no error
        self.assertTrue(paper.pdf.storage.exists(paper.pdf.name))
        self.assertTrue(paper.pdf.storage.exists(paper.pdf_original.name))


class ReplacedUploadTests(MediaCleanupTestCase):
    def _submit(self, paper, upload):
        data = {"title": "Retitled", "abstract": "a", "country_code": "US", 
                "authors_input": '[{"value":"Jane Doe"}]', "topics_input": '[{"value":"Labor Supply"}]'}
        form = PublicationForm(data, {"pdf": upload}, instance=paper)
        self.assertTrue(form.is_valid(), form.errors)
        request = RequestFactory().post("/")
        request.user = CustomUser.objects.create_user(
            email="a@example.com", password="pass12345", first_name="Jane",
            last_name="Doe", is_active=True)
        return process_publication_form(request, form)

    def test_a_new_upload_on_a_pending_paper_deletes_both_old_copies(self):
        paper = self.pending_paper()
        old = {paper.pdf_original.name, paper.pdf.name}
        paper = self._submit(paper, SimpleUploadedFile(
            "second.pdf", tiny_pdf("second"), content_type="application/pdf"))
        paper.refresh_from_db()
        for name in old:
            self.assertFalse(paper.pdf.storage.exists(name), name)
        self.assertTrue(paper.pdf.storage.exists(paper.pdf_original.name))
        self.assertTrue(paper.pdf.storage.exists(paper.pdf.name))
        self.assertEqual(len(files_under(self.media, "publications", "pdf")), 1)
        self.assertEqual(len(files_under(self.media, "publications", "pdf", "original")), 1)

    def test_editing_without_a_new_upload_deletes_nothing(self):
        paper = self.pending_paper()
        before = {paper.pdf_original.name, paper.pdf.name}
        data = {"title": "Retitled", "abstract": "a", "country_code": "US", 
                "authors_input": '[{"value":"Jane Doe"}]', "topics_input": '[{"value":"Labor Supply"}]'}
        form = PublicationForm(data, instance=paper)
        self.assertTrue(form.is_valid(), form.errors)
        request = RequestFactory().post("/")
        request.user = CustomUser.objects.create_user(
            email="b@example.com", password="pass12345", first_name="Jane",
            last_name="Doe", is_active=True)
        process_publication_form(request, form)
        paper.refresh_from_db()
        self.assertEqual({paper.pdf_original.name, paper.pdf.name}, before)
        for name in before:
            self.assertTrue(paper.pdf.storage.exists(name))
        # Regression: editing used to re-save both PDFs under a doubled path each time.
        self.assertEqual(len(files_under(self.media, "publications", "pdf")), 1)
        self.assertEqual(len(files_under(self.media, "publications", "pdf", "original")), 1)
