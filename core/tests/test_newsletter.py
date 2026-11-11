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
        self.assertEqual([i["title"] for i in ctx["new_special_issues"]], ["Open call"])
        self.assertEqual(ctx["new_jobs"] + ctx["due_jobs"], [])
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

    def test_papers_are_only_those_added_since_the_last_issue(self):
        from publications.models import Publication
        from publications.tests.test_models import make_publication

        old = make_publication(title="Old paper", status="approved")
        new = make_publication(title="New paper", status="approved")
        Publication.objects.filter(pk__in=[old.pk, new.pk]).update(pdf="x.pdf")
        EmailCampaign.objects.create(
            kind="newsletter", status="sent", subject="s", html="", text="",
            sent_at=timezone.now() - timedelta(days=1),
            period_start=timezone.now(), period_end=timezone.now())
        Publication.objects.filter(pk=old.pk).update(
            applied_at=timezone.now() - timedelta(days=3))
        for _ in range(5):
            old.record_download()  # popular, but not new: stays out
        new.record_download()
        ctx = newsletter_context()
        self.assertEqual([p["title"] for p in ctx["papers"]], ["New paper"])
        self.assertEqual(ctx["papers"][0]["downloads"], 1)
        self.assertEqual(ctx["papers_heading"], "Most downloaded new papers")
        self.assertIn("Most downloaded new papers</h2>", create_newsletter_campaign().html)

    def test_new_paper_without_downloads_is_listed_and_no_new_papers_hides_the_section(self):
        from publications.models import Publication
        from publications.tests.test_models import make_publication

        paper = make_publication(status="approved")
        Publication.objects.filter(pk=paper.pk).update(pdf="x.pdf")
        self.assertEqual(newsletter_context()["papers"][0]["downloads"], 0)
        EmailCampaign.objects.create(
            kind="newsletter", status="sent", subject="s", html="", text="",
            sent_at=timezone.now() + timedelta(minutes=1),
            period_start=timezone.now(), period_end=timezone.now())
        paper.record_download()  # downloaded, but added before the last issue
        self.assertEqual(newsletter_context()["papers"], [])
        self.assertNotIn("Most downloaded new papers", create_newsletter_campaign().html)

    def test_monthly_is_its_own_issue_with_its_own_numbering_and_window(self):
        from publications.models import Publication
        from publications.tests.test_models import make_publication

        EmailCampaign.objects.create(
            kind="newsletter", status="sent", subject="s", html="", text="",
            sent_at=timezone.now() - timedelta(days=1),
            period_start=timezone.now(), period_end=timezone.now())
        paper = make_publication(status="approved")
        Publication.objects.filter(pk=paper.pk).update(pdf="x.pdf", download_count=3)
        paper.record_download()
        # A weekly send does not move the monthly window or number.
        ctx = newsletter_context("monthly")
        self.assertEqual(ctx["issue_number"], 1)
        self.assertFalse(ctx["first_issue"])
        self.assertEqual([p["title"] for p in ctx["papers"]], [paper.title])
        self.assertAlmostEqual(
            ctx["since"], timezone.now() - timedelta(days=30), delta=timedelta(minutes=1))
        self.assertTrue(ctx["subject"].startswith("The Labor Hub Monthly Newsletter, "))
        campaign = create_newsletter_campaign("monthly")
        self.assertEqual(campaign.kind, "newsletter_monthly")
        self.assertIn("Monthly Newsletter", campaign.html)
        self.assertNotIn("Welcome to", campaign.html)

    def test_new_items_and_deadlines_are_split_and_never_listed_twice(self):
        from events.models import Event
        today = timezone.localdate()
        past = timezone.now() - timedelta(days=20)
        EmailCampaign.objects.create(
            kind="newsletter", status="sent", subject="s", html="", text="",
            sent_at=timezone.now() - timedelta(days=7),
            period_start=timezone.now(), period_end=timezone.now())

        def job(title, days, added):
            j = Job.objects.create(title=title, description="d", url="https://e.com/",
                                   deadline=today + timedelta(days=days), status="approved")
            Job.objects.filter(pk=j.pk).update(created_at=added)

        job("Fresh and soon", 3, timezone.now())
        job("Fresh and far", 30, timezone.now())
        job("Old and soon", 2, past)
        job("Old and far", 10, past)
        ctx = newsletter_context()
        self.assertEqual(sorted(j["title"] for j in ctx["new_jobs"]), ["Fresh and far", "Fresh and soon"])
        self.assertEqual([j["title"] for j in ctx["due_jobs"]], ["Old and soon"])

        # An event with no deadline is still listed as new; one reviewed this week counts as new.
        Event.objects.create(title="No deadline", description="d", status="approved",
                             date=timezone.now() + timedelta(days=30))
        ctx = newsletter_context()
        self.assertEqual([e["title"] for e in ctx["new_events"]], ["No deadline"])
        self.assertEqual(ctx["new_events"][0]["deadline"], "")
        html = create_newsletter_campaign().html
        for marker in (">Job postings</h2>", "Newly Added", "Deadlines This Week"):
            self.assertIn(marker, html)
        self.assertEqual(html.count("Old and soon"), 1)
        self.assertEqual(html.count("Fresh and soon"), 1)
        self.assertNotIn("Old and far", html)

    @override_settings(CM_API_KEY="k", CM_CLIENT_ID="c", CM_NEWSLETTER_LIST_ID="members",
                       CAMPAIGN_FROM_EMAIL="The Labor Hub <digest@ilr.mail.example.edu>")
    def test_send_goes_to_the_weekly_segment_from_the_campaign_address(self):
        with mock.patch("core.management.commands.send_newsletter.CampaignMonitorClient") as cls:
            client = cls.return_value
            client.create_campaign.return_value = "cm1"
            client.segments.return_value = [{"Title": "Newsletter weekly", "SegmentID": "seg-w"}]
            call_command("send_newsletter", "--send", verbosity=0)
        kwargs = client.create_campaign.call_args.kwargs
        self.assertEqual(kwargs["segment_ids"], ["seg-w"])
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


class JobMarketPapersBoxTests(TestCase):
    def setUp(self):
        from publications.models import Publication
        from publications.tests.test_models import make_publication
        self.Publication = Publication
        self.second = make_publication(title="Second JM", status="approved", is_job_market=True)
        self.first = make_publication(title="First JM", status="approved", is_job_market=True)
        self.regular = make_publication(title="Regular paper", status="approved")
        self.pending = make_publication(title="Pending JM", status="pending", is_job_market=True)
        Publication.objects.update(pdf="x.pdf")
        # Numbers are assigned on approval; set them directly so the order is deterministic.
        Publication.objects.filter(pk=self.first.pk).update(job_market_paper_number=1)
        Publication.objects.filter(pk=self.second.pk).update(job_market_paper_number=2)

    def _issue(self, kind="weekly"):
        EmailCampaign.objects.create(
            kind="newsletter", status="sent", subject="s", html="", text="",
            sent_at=timezone.now() - timedelta(days=7),
            period_start=timezone.now(), period_end=timezone.now())
        return create_newsletter_campaign(kind)

    def test_box_lists_only_approved_job_market_papers_in_j_order(self):
        ctx = newsletter_context()
        self.assertEqual([(p["number"], p["title"]) for p in ctx["job_market_papers"]],
                         [("J1", "First JM"), ("J2", "Second JM")])
        html = self._issue().html
        self.assertIn("Job Market Papers</div>", html)
        self.assertLess(html.index("First JM"), html.index("Second JM"))
        self.assertNotIn("Pending JM", html)
        self.assertIn(f"/publications/{self.first.pk}/download/", html)
        self.assertIn("Students on the market can still join the Hub", html)

    def test_box_and_intro_clause_are_left_out_without_job_market_papers(self):
        self.Publication.objects.filter(is_job_market=True).delete()
        html = self._issue().html
        self.assertNotIn("Job Market Papers</div>", html)
        self.assertNotIn("a list of all Job Market Papers", html)
        self.assertIn("new announcements, upcoming deadlines and the most downloaded new papers", html)

    def test_intro_mentions_the_list_and_follows_the_period(self):
        html = self._issue().html
        self.assertIn("This week in the Labor Hub: new announcements, upcoming deadlines, the most downloaded new papers and", html)
        self.assertIn("a list of all Job Market Papers we have received so far", html)
        self.assertIn("Wishing you a great week!", html)
        self.assertIn("Set your alerts", html)
        monthly = create_newsletter_campaign("monthly").html
        self.assertIn("This month in the Labor Hub", monthly)
        self.assertIn("Wishing you a great month!", monthly)
        self.assertIn("New this month", monthly)

    def test_section_order(self):
        from jobs.models import Job
        from special_issues.models import SpecialIssue
        today = timezone.localdate()
        SpecialIssue.objects.create(journal="J", title="Open call", status="approved",
                                    submission_deadline=today + timedelta(days=5))
        Job.objects.create(title="A job", description="d", url="https://e.com/",
                           deadline=today + timedelta(days=5), status="approved")
        from events.models import Event
        Event.objects.create(title="An event", description="d", status="approved",
                             date=timezone.now() + timedelta(days=30),
                             deadline=timezone.now() + timedelta(days=5))
        html = self._issue().html
        order = [html.index(marker) for marker in (
            ">Events</h2>", ">Special issues</h2>", ">Job postings</h2>",
            ">Job Market Papers</div>", ">Long-distance visits</h2>", "How to use the Labor Hub")]
        self.assertEqual(order, sorted(order))
        self.assertNotIn("everything currently open", html)

    def test_text_version_has_the_section(self):
        text = self._issue().text
        self.assertIn("JOB MARKET PAPERS", text)
        self.assertIn("J1. First JM", text)
        self.assertLess(text.index("JOB MARKET PAPERS"), text.index("LONG-DISTANCE VISITS"))
        self.assertLess(text.index("LONG-DISTANCE VISITS"), text.index("HOW TO USE THE LABOR HUB"))

    def test_the_html_stays_well_formed(self):
        import re
        for kind in ("weekly", "monthly"):
            html = self._issue(kind).html
            for tag in ("table", "tr", "td"):
                self.assertEqual(len(re.findall(rf"<{tag}[\s>]", html)),
                                 len(re.findall(rf"</{tag}>", html)), tag)

    def test_first_issue_does_not_promise_the_list_it_already_contains(self):
        html = create_newsletter_campaign().html          # no earlier issue: first_issue
        self.assertIn("Welcome to", html)
        self.assertIn("Job Market Papers</div>", html)
        self.assertNotIn("Coming", html)
