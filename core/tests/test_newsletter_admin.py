from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import EmailCampaign, NewsletterSchedule
from jobs.models import Job
from publications.models import Publication
from publications.tests.test_models import make_publication
from special_issues.models import SpecialIssue

CM = dict(CM_API_KEY="k", CM_CLIENT_ID="c", CM_NEWSLETTER_LIST_ID="news")


def sent(kind="newsletter", ago=timedelta(days=1)):
    when = timezone.now() - ago
    return EmailCampaign.objects.create(
        kind=kind, status="sent", subject="s", html="", text="", sent_at=when,
        period_start=when, period_end=when)


class NewsletterAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser(email="root@example.com", password="pw")
        cls.staff = User.objects.create_user(email="staff@example.com", password="pw", is_staff=True, is_active=True)

    def setUp(self):
        self.client.force_login(self.admin)
        today = timezone.localdate()
        for n in range(8):
            SpecialIssue.objects.create(
                journal="J", title=f"Call {n}", status="approved",
                submission_deadline=today + timedelta(days=n + 1))
        self.paper = make_publication(status="approved")
        Publication.objects.filter(pk=self.paper.pk).update(pdf="x.pdf", download_count=7)
        self.url = reverse("admin:core_newsletterschedule_changelist")

    def test_dashboard_lists_papers_with_downloads_and_greys_out_cut_items(self):
        sent()
        self.paper.record_download()
        response = self.client.get(self.url)
        self.assertContains(response, "Weekly newsletter")
        self.assertContains(response, "Monthly newsletter")
        self.assertContains(response, self.paper.title)
        self.assertContains(response, "the first 6 are emailed")
        self.assertContains(response, "not included", count=4)  # 2 cut items x weekly+monthly

    def test_dashboard_flags_an_empty_issue(self):
        SpecialIssue.objects.all().delete()
        Publication.objects.all().delete()
        self.assertContains(self.client.get(self.url), "the scheduled run would send nothing")

    def test_pause_and_resume_toggle_the_schedule(self):
        toggle = reverse("admin:core_newsletterschedule_toggle", kwargs={"kind": "weekly"})
        self.assertEqual(self.client.get(toggle).status_code, 405)
        self.client.post(toggle)
        schedule = NewsletterSchedule.for_kind("weekly")
        self.assertTrue(schedule.paused)
        self.assertEqual(schedule.paused_by, self.admin)
        self.assertContains(self.client.get(self.url), "Resume scheduled sends")
        self.client.post(toggle)
        self.assertFalse(NewsletterSchedule.for_kind("weekly").paused)

    def test_a_paused_newsletter_is_skipped_by_the_scheduled_run(self):
        NewsletterSchedule.for_kind("weekly").set_paused(True)
        NewsletterSchedule.for_kind("monthly").set_paused(True)
        with override_settings(**CM), \
                mock.patch("core.management.commands.send_newsletter.CampaignMonitorClient") as cls:
            call_command("send_newsletter", "--scheduled", verbosity=0)
        cls.return_value.create_campaign.assert_not_called()

    def test_preview_renders_html_and_stores_nothing(self):
        response = self.client.get(reverse("admin:core_newsletterschedule_preview",
                                           kwargs={"kind": "monthly"}))
        self.assertContains(response, "Monthly Newsletter")
        self.assertEqual(EmailCampaign.objects.count(), 0)
        self.assertEqual(self.client.get(reverse("admin:core_newsletterschedule_preview",
                                                 kwargs={"kind": "daily"})).status_code, 404)

    @override_settings(**CM)
    def test_send_now_confirms_then_sends_once_and_blocks_a_double_send(self):
        send = reverse("admin:core_newsletterschedule_send", kwargs={"kind": "weekly"})
        fake = mock.Mock()
        fake.segments.return_value = [{"Title": "Newsletter weekly", "SegmentID": "seg-w"}]
        fake.create_campaign.return_value = "cm1"
        with mock.patch("accounts.campaigns.CampaignMonitorClient", return_value=fake):
            self.assertContains(self.client.get(send), "right now")
            self.client.post(send)
            fake.send_campaign.assert_called_once()
            self.assertEqual(fake.create_campaign.call_args.kwargs["segment_ids"], ["seg-w"])
            self.assertEqual(EmailCampaign.objects.filter(status="sent").count(), 1)
            # Sent a moment ago: refused even when confirmed.
            response = self.client.post(send, {"send_anyway": "1"})
            self.assertContains(response, "sent a moment ago")
            fake.send_campaign.assert_called_once()

    @override_settings(**CM)
    def test_sending_again_within_the_guard_needs_confirmation(self):
        sent(ago=timedelta(days=2))
        send = reverse("admin:core_newsletterschedule_send", kwargs={"kind": "weekly"})
        fake = mock.Mock()
        fake.segments.return_value = [{"Title": "Newsletter weekly", "SegmentID": "seg-w"}]
        fake.create_campaign.return_value = "cm1"
        with mock.patch("accounts.campaigns.CampaignMonitorClient", return_value=fake):
            self.assertContains(self.client.post(send), "Tick the box")
            fake.send_campaign.assert_not_called()
            self.client.post(send, {"send_anyway": "1"})
            fake.send_campaign.assert_called_once()

    @override_settings(**CM)
    def test_send_test_goes_only_to_the_given_addresses(self):
        test = reverse("admin:core_newsletterschedule_test", kwargs={"kind": "weekly"})
        fake = mock.Mock()
        fake.create_campaign.return_value = "cm1"
        with mock.patch("accounts.campaigns.CampaignMonitorClient", return_value=fake):
            self.assertContains(self.client.get(test), "root@example.com")
            self.client.post(test, {"addresses": "a@example.com, b@example.com"})
            fake.send_preview.assert_called_once_with("cm1", ["a@example.com", "b@example.com"])
            fake.send_campaign.assert_not_called()
            self.assertContains(
                self.client.post(test, {"addresses": ",".join(f"{i}@e.com" for i in range(6))}),
                "1 to 5")
        self.assertFalse(EmailCampaign.objects.filter(status="sent").exists())

    def test_sending_is_disabled_without_campaign_monitor(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Campaign Monitor is not set up")
        send = reverse("admin:core_newsletterschedule_send", kwargs={"kind": "weekly"})
        self.assertEqual(self.client.post(send).status_code, 302)
        self.assertFalse(EmailCampaign.objects.exists())

    def test_staff_without_permission_is_refused(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        toggle = reverse("admin:core_newsletterschedule_toggle", kwargs={"kind": "weekly"})
        self.assertEqual(self.client.post(toggle).status_code, 403)
        self.assertFalse(NewsletterSchedule.objects.filter(paused=True).exists())
