"""Setting Campaign Monitor up by itself: lists found by name, ids remembered, the launch
issue's opt-outs carried over (and never lost), the legacy unsubscribe link."""
from unittest import mock

from django.core import signing
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts import cm_provision, cm_sync
from accounts.models import Profile
from accounts.tests.test_alerts import make_user
from accounts.unsubscribe import LEGACY_SALT
from core import cm_lists
from core.campaign_monitor import CampaignMonitorError
from core.models import CampaignMonitorResource


class FakeSetupClient:
    """Enough of CampaignMonitorClient for cm_provision, with an account's worth of state."""

    def __init__(self, lists=None, unsubscribed=(), fail_unsubscribed=False):
        self.lists_by_name = dict(lists or {})
        self.fields = {}
        self.segment_titles = []
        self.hooks = []
        self.opted_out = list(unsubscribed)
        self.fail_unsubscribed = fail_unsubscribed
        self.created = []

    def lists(self):
        return [{"Name": n, "ListID": i} for n, i in self.lists_by_name.items()]

    def create_list(self, title):
        self.lists_by_name[title] = f"id-{len(self.lists_by_name)}"
        self.created.append(title)
        return self.lists_by_name[title]

    def custom_fields(self, list_id):
        return [{"FieldName": n} for n in self.fields.get(list_id, [])]

    def create_custom_field(self, list_id, name):
        self.fields.setdefault(list_id, []).append(name)

    def segments(self, list_id):
        return [{"Title": t, "SegmentID": t} for t in self.segment_titles]

    def create_segment(self, list_id, title, rules):
        self.segment_titles.append(title)
        return title

    def webhooks(self, list_id):
        return [h for h in self.hooks if h["ListID"] == list_id]

    def create_webhook(self, list_id, url, events=()):
        self.hooks.append({"ListID": list_id, "Url": url})

    def all_unsubscribed(self, list_id):
        if self.fail_unsubscribed:
            raise CampaignMonitorError("down", status=500)
        return iter(self.opted_out)


@override_settings(SITE_URL="https://example.edu", CM_WEBHOOK_SECRET="s3cret")
class EnsureResourcesTests(TestCase):
    def test_creates_both_lists_fields_segments_and_webhooks_and_remembers_the_ids(self):
        client = FakeSetupClient()
        ids = cm_provision.ensure_resources(client)
        self.assertEqual(set(client.created), {"Labor Hub Newsletter", "Labor Hub Alerts"})
        self.assertEqual(client.segment_titles, ["Newsletter weekly", "Newsletter monthly"])
        self.assertEqual(len(client.hooks), 2)
        self.assertTrue(all("s3cret" in h["Url"] for h in client.hooks))
        self.assertEqual(cm_lists.list_id(cm_lists.NEWSLETTER), ids["newsletter"])
        self.assertEqual(cm_lists.list_id(cm_lists.ALERTS), ids["alerts"])
        self.assertTrue(cm_lists.provisioned())

    def test_running_it_again_creates_nothing_new(self):
        client = FakeSetupClient()
        cm_provision.ensure_resources(client)
        created, hooks, segments = len(client.created), len(client.hooks), len(client.segment_titles)
        cm_provision.ensure_resources(client)
        self.assertEqual((len(client.created), len(client.hooks), len(client.segment_titles)),
                         (created, hooks, segments))

    def test_an_existing_list_is_found_by_name(self):
        client = FakeSetupClient(lists={"Labor Hub Alerts": "existing-alerts"})
        ids = cm_provision.ensure_resources(client)
        self.assertEqual(ids["alerts"], "existing-alerts")
        self.assertNotIn("Labor Hub Alerts", client.created)

    def test_a_setting_overrides_the_stored_id(self):
        cm_lists.remember(cm_lists.NEWSLETTER, "stored")
        with override_settings(CM_NEWSLETTER_LIST_ID="from-env"):
            self.assertEqual(cm_lists.list_id(cm_lists.NEWSLETTER), "from-env")
        self.assertEqual(cm_lists.list_id(cm_lists.NEWSLETTER), "stored")

    @override_settings(SITE_URL="http://localhost:8000")
    def test_webhooks_are_skipped_without_a_public_https_address(self):
        client = FakeSetupClient()
        cm_provision.ensure_resources(client)
        self.assertEqual(client.hooks, [])


class LaunchOptOutTests(TestCase):
    def test_members_who_unsubscribed_from_the_launch_issue_are_switched_off(self):
        gone = make_user("gone@example.com")
        stays = make_user("stays@example.com")
        client = FakeSetupClient(
            lists={"Labor Hub Members": "interim"}, unsubscribed=["GONE@example.com", "ghost@x.org"])
        cm_provision.ensure_resources(client)
        self.assertEqual(Profile.objects.get(user=gone).newsletter_frequency, "off")
        self.assertEqual(Profile.objects.get(user=stays).newsletter_frequency, "weekly")

    def test_a_failed_import_leaves_the_newsletter_list_unrecorded_and_nothing_is_pushed(self):
        make_user("gone@example.com")
        client = FakeSetupClient(lists={"Labor Hub Members": "interim"}, fail_unsubscribed=True)
        with self.assertRaises(CampaignMonitorError):
            cm_provision.ensure_resources(client)
        self.assertEqual(cm_lists.list_id(cm_lists.NEWSLETTER), "")
        # The alerts list may already be known, but members are held back from both.
        self.assertFalse(cm_lists.provisioned())
        pushed = FakeSetupClient()
        with override_settings(CAMPAIGN_DELIVERY="cm", CM_API_KEY="k", CM_CLIENT_ID="c"):
            profile = Profile.objects.get()
            self.assertFalse(cm_sync.sync_profile(profile, client=pushed))

    def test_the_import_happens_once(self):
        client = FakeSetupClient(lists={"Labor Hub Members": "interim"}, unsubscribed=[])
        cm_provision.ensure_resources(client)
        client.opted_out = ["late@example.com"]
        user = make_user("late@example.com")
        cm_provision.ensure_resources(client)
        self.assertEqual(Profile.objects.get(user=user).newsletter_frequency, "weekly")
        self.assertTrue(CampaignMonitorResource.objects.filter(key="launch_optouts_imported").exists())

    def test_no_interim_list_means_nothing_to_import(self):
        self.assertEqual(cm_provision.import_launch_optouts(FakeSetupClient(), lambda m: None), 0)


class CmSetupCommandTests(TestCase):
    @override_settings(CM_API_KEY="", CM_CLIENT_ID="")
    def test_is_a_noop_with_if_configured_and_an_error_without(self):
        call_command("cm_setup", "--if-configured", verbosity=0)
        with self.assertRaises(CommandError):
            call_command("cm_setup", verbosity=0)

    @override_settings(CM_API_KEY="k", CM_CLIENT_ID="c", SITE_URL="https://example.edu")
    def test_runs_setup_with_the_real_client_class(self):
        with mock.patch("accounts.management.commands.cm_setup.CampaignMonitorClient",
                        return_value=FakeSetupClient()):
            call_command("cm_setup", verbosity=0)
        self.assertTrue(cm_lists.provisioned())


class NewsletterSettingTests(TestCase):
    def test_a_new_member_defaults_to_the_weekly_newsletter(self):
        self.assertEqual(make_user("new@example.com").profile.newsletter_frequency, "weekly")

    def test_the_old_per_user_digest_link_still_turns_the_newsletter_off(self):
        user = make_user("old@example.com")
        token = signing.dumps({"uid": user.pk}, salt=LEGACY_SALT)
        for url in (reverse("newsletter_unsubscribe", args=[token]),
                    f"/accounts/digest/unsubscribe/{token}/"):
            Profile.objects.filter(user=user).update(newsletter_frequency="weekly")
            response = self.client.get(url)
            self.assertContains(response, "unsubscribed")
            self.assertEqual(Profile.objects.get(user=user).newsletter_frequency, "off")

    def test_a_bad_unsubscribe_link_changes_nothing(self):
        user = make_user("old@example.com")
        response = self.client.get(reverse("newsletter_unsubscribe", args=["junk"]))
        self.assertContains(response, "expired or invalid")
        self.assertEqual(Profile.objects.get(user=user).newsletter_frequency, "weekly")

    def test_saving_the_setting_allows_resubscribing_that_list(self):
        user = make_user("a@example.com")
        Profile.objects.filter(user=user).update(newsletter_frequency="off")
        self.client.force_login(user)
        with mock.patch("accounts.cm_sync.sync_profile") as sync, \
                self.captureOnCommitCallbacks(execute=True), \
                override_settings(CAMPAIGN_DELIVERY="cm", CM_API_KEY="k", CM_CLIENT_ID="c",
                                  CM_NEWSLETTER_LIST_ID="n", CM_ALERT_LIST_ID="a"):
            self.client.post(reverse("settings"), {
                "save_notifications": "1", "newsletter_frequency": "monthly"})
        profile = sync.call_args.args[0]
        self.assertEqual(profile.newsletter_frequency, "monthly")
        self.assertEqual(profile.cm_resubscribe, {"newsletter"})
