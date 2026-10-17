"""Approving a paper is all-or-nothing: no "approved but no cover" half state."""
import os
import shutil
import tempfile
from unittest import mock

from django.contrib.messages import get_messages
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import CustomUser
from publications.models import Publication
from publications.tests.test_media_cleanup import tiny_pdf


@override_settings()
class AtomicApprovalTests(TestCase):
    def setUp(self):
        media = tempfile.mkdtemp(prefix="laborhub-atomic-")
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        self.admin = CustomUser.objects.create_superuser(
            email="admin@example.com", password="pass12345", first_name="A", last_name="D")

    def pending(self, title="Paper", job_market=False):
        paper = Publication.objects.create(
            title=title, abstract="a", status="pending", is_job_market=job_market)
        paper.pdf_original.save("mine.pdf", ContentFile(tiny_pdf()), save=False)
        paper.pdf.save("mine.pdf", ContentFile(tiny_pdf()), save=True)
        return paper

    def test_a_failing_cover_leaves_the_paper_pending_and_the_number_unused(self):
        paper = self.pending()
        with mock.patch.object(Publication, "rebuild_covered_pdf", side_effect=RuntimeError("merge died")):
            with self.assertRaises(RuntimeError):
                paper.approve(self.admin)
        paper.refresh_from_db()
        self.assertEqual(paper.status, "pending")
        self.assertIsNone(paper.discussion_paper_number)
        self.assertIsNone(paper.reviewed_at)

        # The number was not consumed: the retry gets it.
        paper.approve(self.admin)
        paper.refresh_from_db()
        self.assertEqual((paper.status, paper.discussion_paper_number), ("approved", 1))
        self.assertTrue(paper.pdf.name.rsplit("/", 1)[-1].startswith("DP1-"))

    def test_the_in_memory_object_is_reset_too(self):
        paper = self.pending()
        with mock.patch.object(Publication, "rebuild_covered_pdf", side_effect=RuntimeError("x")):
            with self.assertRaises(RuntimeError):
                paper.approve(self.admin)
        self.assertEqual(paper.status, "pending")
        self.assertIsNone(paper.discussion_paper_number)

    def test_job_market_numbers_roll_back_too(self):
        paper = self.pending(job_market=True)
        with mock.patch.object(Publication, "rebuild_covered_pdf", side_effect=RuntimeError("x")):
            with self.assertRaises(RuntimeError):
                paper.approve(self.admin)
        paper.refresh_from_db()
        self.assertIsNone(paper.job_market_paper_number)
        paper.approve(self.admin)
        paper.refresh_from_db()
        self.assertEqual(paper.job_market_paper_number, 1)

    def test_a_good_approval_still_numbers_and_covers(self):
        paper = self.pending()
        paper.approve(self.admin)
        paper.refresh_from_db()
        self.assertEqual((paper.status, paper.discussion_paper_number), ("approved", 1))
        self.assertEqual(paper.reviewed_by, self.admin)
        self.assertTrue(paper.pdf.storage.exists(paper.pdf.name))

    def test_approving_twice_is_still_refused(self):
        paper = self.pending()
        paper.approve(self.admin)
        with self.assertRaises(ValueError):
            paper.approve(self.admin)

    def test_admin_view_reports_a_failure_and_leaves_the_paper_pending(self):
        paper = self.pending()
        self.client.force_login(self.admin)
        url = reverse("admin:publications_publication_approve", args=[paper.pk])
        with mock.patch.object(Publication, "rebuild_covered_pdf", side_effect=RuntimeError("merge died")):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # back to the list, not a 500
        message = " ".join(str(m) for m in get_messages(response.wsgi_request))
        self.assertIn("Could not approve", message)
        self.assertIn("merge died", message)
        self.assertIn("left pending", message)
        paper.refresh_from_db()
        self.assertEqual(paper.status, "pending")

        response = self.client.get(url)  # retry once the problem is gone
        paper.refresh_from_db()
        self.assertEqual(paper.status, "approved")
