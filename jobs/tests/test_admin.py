from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from jobs.models import Job


class JobAdminApprovalTests(TestCase):
    """Exercises the shared core.admin.ApprovableAdmin workflow via the Job admin."""

    def setUp(self):
        self.admin = CustomUser.objects.create_superuser(
            email="admin@example.com", password="pw12345",
            first_name="Ad", last_name="Min",
        )
        self.client.force_login(self.admin)

    def _job(self, status="pending"):
        return Job.objects.create(
            title="Job", description="d", url="https://e.com",
            deadline=date(2030, 1, 1), status=status,
        )

    def test_changelist_renders(self):
        self._job()
        response = self.client.get(reverse("admin:jobs_job_changelist"))
        self.assertEqual(response.status_code, 200)

    def test_approve_button_approves_job(self):
        job = self._job()
        response = self.client.get(reverse("admin:jobs_job_approve", args=[job.pk]))
        self.assertEqual(response.status_code, 302)
        job.refresh_from_db()
        self.assertEqual(job.status, "approved")
        self.assertEqual(job.reviewed_by, self.admin)

    def test_reject_button_rejects_job(self):
        job = self._job()
        self.client.get(reverse("admin:jobs_job_reject", args=[job.pk]))
        job.refresh_from_db()
        self.assertEqual(job.status, "rejected")

    def test_bulk_approve_action(self):
        j1 = self._job()
        j2 = self._job()
        response = self.client.post(reverse("admin:jobs_job_changelist"), {
            "action": "approve_selected",
            "_selected_action": [j1.pk, j2.pk],
        })
        self.assertEqual(response.status_code, 302)
        j1.refresh_from_db()
        j2.refresh_from_db()
        self.assertEqual(j1.status, "approved")
        self.assertEqual(j2.status, "approved")
