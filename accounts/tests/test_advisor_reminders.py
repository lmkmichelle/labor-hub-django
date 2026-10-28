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
        self.assertEqual(len(self.run_cmd()), 1)
        self.assertEqual(self.run_cmd(), [])

    def test_escalates_to_admin_inbox_after_fourteen_days_once(self):
        self.aged(14)
        out = self.run_cmd()
        self.assertEqual([m.to for m in out], [["ega@example.com"]])
        self.assertIn("has not responded", out[0].body)
        self.assertEqual(self.run_cmd(), [])

    def test_decided_applications_are_skipped(self):
        self.aged(20, status=UserApplication.Status.REJECTED)
        self.assertEqual(self.run_cmd(), [])
