from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.tests.test_advisee_views import make_researcher
from publications.models import Publication
from publications.tests.test_models import make_publication


class PaperAdvisorReminderTests(TestCase):
    def setUp(self):
        self.advisor = make_researcher()

    def paper(self, days, **kw):
        fields = dict(is_job_market=True, jm_advisor=self.advisor)
        fields.update(kw)
        paper = make_publication(**fields)
        Publication.objects.filter(pk=paper.pk).update(
            applied_at=timezone.now() - timedelta(days=days))
        return paper

    def run_cmd(self):
        mail.outbox = []
        call_command("remind_advisors", verbosity=0)
        return mail.outbox

    def test_no_reminder_before_seven_days(self):
        self.paper(6)
        self.assertEqual(self.run_cmd(), [])

    def test_one_reminder_at_seven_days_and_never_a_second(self):
        paper = self.paper(7, title="My JMP")
        out = self.run_cmd()
        self.assertEqual([m.to for m in out], [[self.advisor.email]])
        self.assertTrue(out[0].subject.startswith("Reminder: [Action Required]"))
        self.assertIn("My JMP", out[0].subject)
        paper.refresh_from_db()
        self.assertIsNotNone(paper.jm_advisor_reminded_at)
        self.assertEqual(self.run_cmd(), [])

    def test_no_reminder_once_the_advisor_has_responded_or_the_paper_is_decided(self):
        self.paper(10, jm_advisor_acknowledged=True)
        self.paper(10, jm_advisor_acknowledged=False)
        self.paper(10, status="approved")
        self.paper(10, status="rejected")
        self.paper(10, is_job_market=False)
        self.assertEqual(self.run_cmd(), [])

    def test_dry_run_sends_and_records_nothing(self):
        paper = self.paper(8)
        mail.outbox = []
        call_command("remind_advisors", "--dry-run", verbosity=0)
        self.assertEqual(mail.outbox, [])
        paper.refresh_from_db()
        self.assertIsNone(paper.jm_advisor_reminded_at)
