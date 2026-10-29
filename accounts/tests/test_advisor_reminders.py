from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import UserApplication
from accounts.tests.test_advisee_views import make_researcher, make_student_application


@override_settings(ADMIN_NOTIFY_EMAIL="ega@example.com")
class RemindAdvisorsTests(TestCase):
    def aged(self, days, **kw):
        app = make_student_application(make_researcher(), **kw)
        UserApplication.objects.filter(pk=app.pk).update(
            applied_at=timezone.now() - timedelta(days=days))
        return app

    def run_cmd(self):
        mail.outbox = []
        call_command("remind_advisors", verbosity=0)
        return mail.outbox

    def test_nothing_before_three_days(self):
        self.aged(2)
        self.assertEqual(self.run_cmd(), [])

    def test_reminders_at_three_and_seven_days_once_each(self):
        app = self.aged(3)
        out = self.run_cmd()
        self.assertEqual([m.to for m in out], [["advisor@example.com"]])
        self.assertTrue(out[0].subject.startswith("Reminder:"))
        self.assertEqual(self.run_cmd(), [])
        UserApplication.objects.filter(pk=app.pk).update(
            applied_at=timezone.now() - timedelta(days=7))
        out = self.run_cmd()
        # The advisor's second reminder, plus the student's one-off note (below).
        self.assertEqual(sorted(m.to[0] for m in out),
                         ["advisor@example.com", "student@example.com"])
        self.assertEqual(self.run_cmd(), [])

    def test_escalates_to_admin_inbox_after_fourteen_days_once(self):
        self.aged(14)
        out = self.run_cmd()
        escalation = [m for m in out if m.to == ["ega@example.com"]]
        self.assertEqual(len(escalation), 1)
        self.assertIn("has not responded", escalation[0].body)
        self.assertEqual(self.run_cmd(), [])

    def test_student_told_once_at_seven_days_and_not_before(self):
        app = self.aged(6)
        self.assertEqual([m.to for m in self.run_cmd() if m.to == ["student@example.com"]], [])
        UserApplication.objects.filter(pk=app.pk).update(
            applied_at=timezone.now() - timedelta(days=7))
        told = [m for m in self.run_cmd() if m.to == ["student@example.com"]]
        self.assertEqual(len(told), 1)
        self.assertEqual(told[0].subject, "Your Labor Hub application is waiting for your advisor")
        self.assertIn("Adam Advisor", told[0].body)
        self.assertEqual([m for m in self.run_cmd() if m.to == ["student@example.com"]], [])

    def test_dry_run_sends_nothing_and_changes_nothing(self):
        app = self.aged(15)
        mail.outbox = []
        call_command("remind_advisors", "--dry-run", verbosity=0)
        self.assertEqual(mail.outbox, [])
        app.refresh_from_db()
        self.assertIsNone(app.student_reminded_at)

    def test_decided_applications_are_skipped(self):
        self.aged(20, status=UserApplication.Status.REJECTED)
        self.assertEqual(self.run_cmd(), [])
