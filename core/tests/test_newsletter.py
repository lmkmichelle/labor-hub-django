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

    def test_welcome_and_next_week_blocks_are_for_the_first_issue_only(self):
        first = create_newsletter_campaign()
        self.assertIn("Welcome to", first.html)
        self.assertIn("Coming", first.html)
        self.assertIn("COMING NEXT WEEK", first.text)
        EmailCampaign.objects.create(
            kind="newsletter", status="sent", subject="s", html="", text="",
            period_start=timezone.now(), period_end=timezone.now())
        second = create_newsletter_campaign()
        for text in ("Welcome to", "Job Market Papers", "Coming"):
            self.assertNotIn(text, second.html)
        self.assertNotIn("COMING NEXT WEEK", second.text)
        self.assertNotIn("Thank you for joining", second.text)

    def test_papers_fall_back_to_all_time_when_the_week_is_quiet(self):
        from publications.models import Publication
        from publications.tests.test_models import make_publication

        paper = make_publication(status="approved")
        Publication.objects.filter(pk=paper.pk).update(pdf="x.pdf", download_count=7)
        ctx = newsletter_context()
        self.assertEqual([p["title"] for p in ctx["papers"]], [paper.title])
        self.assertEqual(ctx["papers_heading"], "Most downloaded papers")

        # Issue No. 1 stays all-time even when there are downloads this week...
        paper.record_download()
        self.assertEqual(newsletter_context()["papers_heading"], "Most downloaded papers")
        html = create_newsletter_campaign().html
        self.assertIn("Most downloaded papers</h2>", html)
        self.assertNotIn("this week</h2>", html)

        # ...and from the second issue on, a week with downloads is ranked by the week.
        EmailCampaign.objects.create(
            kind="newsletter", status="sent", subject="s", html="", text="",
            period_start=timezone.now(), period_end=timezone.now())
        ctx = newsletter_context()
        self.assertEqual(ctx["papers_heading"], "Most downloaded papers this week")
        self.assertIn("Most downloaded papers this week", create_newsletter_campaign().html)

    @override_settings(CM_API_KEY="k", CM_CLIENT_ID="c", CM_NEWSLETTER_LIST_ID="members",
                       CAMPAIGN_FROM_EMAIL="The Labor Hub <digest@ilr.mail.example.edu>")
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

    @override_settings(CM_API_KEY="k", CM_CLIENT_ID="c", CM_NEWSLETTER_LIST_ID="members")
    def test_test_to_sends_only_a_preview_and_is_not_marked_sent(self):
        with mock.patch("core.management.commands.send_newsletter.CampaignMonitorClient") as cls:
            cls.return_value.create_campaign.return_value = "cm1"
            call_command("send_newsletter", "--test-to", "me@example.com", verbosity=0)
        cls.return_value.send_preview.assert_called_once_with("cm1", ["me@example.com"])
        cls.return_value.send_campaign.assert_not_called()
        self.assertNotEqual(EmailCampaign.objects.get().status, "sent")

    @override_settings(CM_API_KEY="k", CM_CLIENT_ID="c", CM_NEWSLETTER_LIST_ID="members")
    def test_test_to_accepts_several_addresses_up_to_five(self):
        with mock.patch("core.management.commands.send_newsletter.CampaignMonitorClient") as cls:
            cls.return_value.create_campaign.return_value = "cm1"
            call_command("send_newsletter", "--test-to", "a@example.com, b@example.com,c@example.com",
                         verbosity=0)
            cls.return_value.send_preview.assert_called_once_with(
                "cm1", ["a@example.com", "b@example.com", "c@example.com"])
            with self.assertRaises(CommandError):
                call_command("send_newsletter", "--test-to",
                             ",".join(f"{i}@example.com" for i in range(6)), verbosity=0)

    def test_requires_exactly_one_mode(self):
        with self.assertRaises(CommandError):
            call_command("send_newsletter")
