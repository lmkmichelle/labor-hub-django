from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import EmailCampaign
from core.newsletter import create_newsletter_campaign, newsletter_context
from jobs.models import Job
from special_issues.models import SpecialIssue


class NewsletterTests(TestCase):
    def setUp(self):
        today = timezone.localdate()
        SpecialIssue.objects.create(
            journal="J", title="Open call", status="approved",
            submission_deadline=today + timedelta(days=5))
        SpecialIssue.objects.create(
            journal="J", title="Closed call", status="approved",
            submission_deadline=today - timedelta(days=1))
        Job.objects.create(title="Pending job", description="x", url="https://e.com/",
                           deadline=today + timedelta(days=5), status="pending")

    def test_only_open_approved_items_and_empty_sections_hidden(self):
        ctx = newsletter_context()
        self.assertEqual([i["title"] for i in ctx["special_issues"]], ["Open call"])
        self.assertEqual(ctx["jobs"], [])
        html = create_newsletter_campaign().html
        self.assertIn("Open call", html)
        self.assertNotIn("Closed call", html)
        self.assertNotIn(">Job postings</h2>", html)
        self.assertNotIn("Georgia", html)
        self.assertIn("<unsubscribe", html)

    def test_issue_number_counts_sent_issues(self):
        self.assertEqual(newsletter_context()["issue_number"], 1)
        EmailCampaign.objects.create(
            kind="newsletter", status="sent", subject="s", html="", text="",
            period_start=timezone.now(), period_end=timezone.now())
        self.assertEqual(newsletter_context()["issue_number"], 2)

    @override_settings(CM_API_KEY="k", CM_CLIENT_ID="c", CM_MEMBERS_LIST_ID="members",
                       DIGEST_FROM_EMAIL="The Labor Hub <digest@ilr.mail.example.edu>")
    def test_send_goes_to_members_list_from_digest_address(self):
        with mock.patch("core.management.commands.send_newsletter.CampaignMonitorClient") as cls:
            client = cls.return_value
            client.create_campaign.return_value = "cm1"
            call_command("send_newsletter", "--send", verbosity=0)
        kwargs = client.create_campaign.call_args.kwargs
        self.assertEqual(kwargs["list_ids"], ["members"])
        self.assertEqual(kwargs["from_email"], "digest@ilr.mail.example.edu")
        client.send_campaign.assert_called_once()
        self.assertEqual(EmailCampaign.objects.get().status, "sent")

    @override_settings(CM_API_KEY="k", CM_CLIENT_ID="c", CM_MEMBERS_LIST_ID="members")
    def test_test_to_sends_only_a_preview_and_is_not_marked_sent(self):
        with mock.patch("core.management.commands.send_newsletter.CampaignMonitorClient") as cls:
            cls.return_value.create_campaign.return_value = "cm1"
            call_command("send_newsletter", "--test-to", "me@example.com", verbosity=0)
        cls.return_value.send_preview.assert_called_once_with("cm1", ["me@example.com"])
        cls.return_value.send_campaign.assert_not_called()
        self.assertNotEqual(EmailCampaign.objects.get().status, "sent")

    def test_requires_exactly_one_mode(self):
        with self.assertRaises(CommandError):
            call_command("send_newsletter")
