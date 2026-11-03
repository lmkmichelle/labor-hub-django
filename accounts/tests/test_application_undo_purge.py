from datetime import timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth.hashers import make_password
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser, ResearchPaper, UserApplication


def make_application(email="app@example.com", status="pending", role=CustomUser.Role.RESEARCHER,
                     advisor=None, rejected_days_ago=None, samples=1, resume=True):
    app = UserApplication.objects.create(
        email=email, first_name="Ann", last_name="Applicant", role=role, position="Prof",
        department="Econ", password=make_password("pass12345"), country_code="US",
        advisor=advisor, status=status)
    if resume:
        app.resume.save("cv.pdf", SimpleUploadedFile("cv.pdf", b"%PDF cv"), save=True)
    for n in range(samples):
        ResearchPaper.objects.create(
            application=app, paper=SimpleUploadedFile(f"s{n}.pdf", b"%PDF sample"))
    if rejected_days_ago is not None:
        UserApplication.objects.filter(pk=app.pk).update(
            status="rejected", reviewed_at=timezone.now() - timedelta(days=rejected_days_ago))
        app.refresh_from_db()
    return app


class UndoRejectionTests(TestCase):
    def test_undo_approves_creates_account_and_sends_the_acceptance_email(self):
        app = make_application(rejected_days_ago=3)
        user = app.undo_rejection()
        app.refresh_from_db()
        self.assertEqual(app.status, "approved")
        self.assertTrue(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Your Labor Hub application has been approved")

    def test_only_rejected_applications_can_be_undone(self):
        for status in ("pending", "approved"):
            app = make_application(email=f"{status}@example.com", status=status)
            with self.assertRaises(ValueError):
                app.undo_rejection()

    def test_a_conflicting_account_leaves_it_rejected(self):
        app = make_application(rejected_days_ago=3)
        CustomUser.objects.create_user(email=app.email, password="x", is_active=True)
        with self.assertRaises(ValueError):
            app.undo_rejection()
        app.refresh_from_db()
        self.assertEqual(app.status, "rejected")
        self.assertEqual(mail.outbox, [])

    def test_undo_works_after_the_files_were_purged(self):
        app = make_application(rejected_days_ago=40)
        call_command("purge_application_files", stdout=StringIO())
        app.refresh_from_db()
        self.assertIsNotNone(app.files_purged_at)
        app.undo_rejection()
        app.refresh_from_db()
        self.assertEqual(app.status, "approved")

    def test_admin_undo_button_and_url(self):
        admin_user = CustomUser.objects.create_superuser(email="root@example.com", password="pw")
        self.client.force_login(admin_user)
        app = make_application(rejected_days_ago=2)
        change = reverse("admin:accounts_userapplication_change", args=[app.pk])
        self.assertContains(self.client.get(change), "Undo rejection (approve)")
        self.assertContains(self.client.get(change), "Kept until")
        self.client.get(reverse("admin:undo_rejection_application", args=[app.pk]))
        app.refresh_from_db()
        self.assertEqual(app.status, "approved")
        self.assertEqual(len(mail.outbox), 1)

    def test_advisor_can_undo_a_decline_for_their_own_advisee_only(self):
        advisor = CustomUser.objects.create_user(
            email="adv@example.com", password="x", is_active=True, role=CustomUser.Role.RESEARCHER)
        other = CustomUser.objects.create_user(
            email="oth@example.com", password="x", is_active=True, role=CustomUser.Role.RESEARCHER)
        app = make_application(email="stu@example.com", role=CustomUser.Role.STUDENT,
                               advisor=advisor, rejected_days_ago=2)
        url = reverse("advisee_undo_reject", args=[app.pk])
        self.client.force_login(other)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(advisor)
        page = self.client.get(reverse("advisee_applications"))
        self.assertContains(page, "Undo decline (approve)")
        self.client.post(url)
        app.refresh_from_db()
        self.assertEqual(app.status, "approved")
        self.assertEqual(CustomUser.objects.get(email="stu@example.com").advisor, advisor)


class ApplicationFilePurgeTests(TestCase):
    def test_approving_deletes_samples_but_keeps_the_resume(self):
        app = make_application()
        app.approve()
        app.refresh_from_db()
        self.assertFalse(app.research_papers.exists())
        self.assertTrue(app.resume)
        self.assertIsNotNone(app.files_purged_at)

    def test_a_storage_failure_never_breaks_approval(self):
        app = make_application()
        with mock.patch("accounts.models.ResearchPaper.delete", side_effect=OSError("down")):
            app.approve()
        app.refresh_from_db()
        self.assertEqual(app.status, "approved")
        self.assertIsNone(app.files_purged_at)
        self.assertTrue(app.research_papers.exists())

    def test_purge_removes_rejected_after_30_days_only(self):
        old = make_application(email="old@example.com", rejected_days_ago=31)
        recent = make_application(email="new@example.com", rejected_days_ago=10)
        pending = make_application(email="pend@example.com")
        call_command("purge_application_files", stdout=StringIO())
        for app in (old, recent, pending):
            app.refresh_from_db()
        self.assertFalse(old.research_papers.exists())
        self.assertFalse(old.resume)
        self.assertIsNotNone(old.files_purged_at)
        self.assertTrue(recent.research_papers.exists())
        self.assertTrue(recent.resume)
        self.assertTrue(pending.research_papers.exists())
        self.assertIsNone(pending.files_purged_at)

    def test_purge_backfills_older_approvals_and_keeps_their_resume(self):
        app = make_application(status="approved")
        call_command("purge_application_files", stdout=StringIO())
        app.refresh_from_db()
        self.assertFalse(app.research_papers.exists())
        self.assertTrue(app.resume)

    def test_dry_run_deletes_nothing(self):
        app = make_application(rejected_days_ago=45)
        out = StringIO()
        call_command("purge_application_files", "--dry-run", stdout=out)
        app.refresh_from_db()
        self.assertTrue(app.research_papers.exists())
        self.assertTrue(app.resume)
        self.assertIn("would clean", out.getvalue())
