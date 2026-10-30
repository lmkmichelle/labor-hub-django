"""Newsletter/alerts as Campaign Monitor campaigns: client, list sync, webhook, campaigns."""
import json
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts import campaigns, cm_sync
from accounts.models import CustomUser, Profile
from accounts.tests.test_alerts import make_publication, make_user, make_visit
from core.campaign_monitor import CampaignMonitorClient, CampaignMonitorError
from core.models import EmailCampaign
from special_issues.models import SpecialIssue

CM = dict(
    CAMPAIGN_DELIVERY="cm", CM_API_KEY="key", CM_CLIENT_ID="client",
    CM_NEWSLETTER_LIST_ID="newsletter-list", CM_ALERT_LIST_ID="alert-list",
    CM_WEBHOOK_SECRET="s3cret", SITE_URL="http://testserver",
)


class FakeClient:
    """Records calls; stands in for CampaignMonitorClient."""

    def __init__(self):
        self.calls = []
        self.newsletter_segments = [{"Title": "Newsletter weekly", "SegmentID": "seg-weekly"},
                                    {"Title": "Newsletter monthly", "SegmentID": "seg-monthly"}]
        self.alert_segments = []
        self.fail = False

    def _log(self, call, *args, **kwargs):
        if self.fail:
            raise CampaignMonitorError("down", status=500)
        self.calls.append((call, args, kwargs))

    def upsert_subscriber(self, *a, **k):
        self._log("upsert", *a, **k)

    def unsubscribe(self, *a, **k):
        self._log("unsubscribe", *a, **k)

    def segments(self, list_id):
        return self.newsletter_segments if list_id == "newsletter-list" else list(self.alert_segments)

    def delete_segment(self, segment_id):
        self._log("delete_segment", segment_id)

    def create_segment(self, list_id, title, rule_groups):
        self._log("create_segment", list_id, title, rule_groups)
        return f"id-{title}"

    def create_campaign(self, **kwargs):
        self._log("create_campaign", **kwargs)
        return "cm-campaign-1"

    def send_campaign(self, *a, **k):
        self._log("send_campaign", *a, **k)

    def names(self):
        return [c[0] for c in self.calls]


class ClientTests(TestCase):
    def _urlopen(self, body=b"{}"):
        response = mock.MagicMock()
        response.read.return_value = body
        response.__enter__.return_value = response
        return mock.patch("urllib.request.urlopen", return_value=response)

    def test_basic_auth_and_json_body(self):
        with self._urlopen(b'"abc"') as urlopen:
            result = CampaignMonitorClient("my-key", "cid").create_segment("L", "T", [[("[F]", "EQUALS x")]])
        request = urlopen.call_args[0][0]
        self.assertEqual(result, "abc")
        self.assertTrue(request.full_url.endswith("/segments/L.json"))
        self.assertTrue(request.get_header("Authorization").startswith("Basic "))
        self.assertEqual(json.loads(request.data)["RuleGroups"][0]["Rules"][0],
                         {"RuleType": "[F]", "Clause": "EQUALS x"})

    def test_http_error_becomes_campaign_monitor_error(self):
        import io
        import urllib.error
        error = urllib.error.HTTPError(
            "u", 400, "bad", {}, io.BytesIO(b'{"Code": 203, "Message": "Not on list"}'))
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(CampaignMonitorError) as ctx:
                CampaignMonitorClient("k", "c").unsubscribe("L", "a@b.com")
        self.assertEqual((ctx.exception.status, ctx.exception.code), (400, 203))

    def test_network_failure_becomes_campaign_monitor_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("boom")):
            with self.assertRaises(CampaignMonitorError):
                CampaignMonitorClient("k", "c").lists()


@override_settings(**CM)
class TokenAndSyncTests(TestCase):
    def test_alert_tokens_are_delimited_and_sorted(self):
        profile = make_user(topics=["Labor Supply", "Migration"], countries=["US"], universities=[7]).profile
        values = cm_sync.alert_field_values(profile)
        self.assertEqual(values[cm_sync.TOPICS_FIELD], "|t:labor-supply|t:migration|")
        self.assertEqual(values[cm_sync.COUNTRIES_FIELD], "|c:US|")
        self.assertEqual(values[cm_sync.INSTITUTIONS_FIELD], "|u:7|")

    def test_subscribes_to_the_lists_the_member_chose_and_is_idempotent(self):
        client = FakeClient()
        user = make_user(topics=["Migration"])
        profile = Profile.objects.get(pk=user.profile.pk)
        self.assertEqual(profile.newsletter_frequency, "weekly")  # the default
        self.assertTrue(cm_sync.sync_profile(profile, client=client))
        upserts = [c for c in client.calls if c[0] == "upsert"]
        self.assertEqual({c[1][0] for c in upserts}, {"newsletter-list", "alert-list"})
        self.assertFalse(cm_sync.sync_profile(profile, client=client))  # unchanged: no calls

    def test_member_who_wants_nothing_costs_no_api_call_on_first_sync(self):
        client = FakeClient()
        profile = make_user().profile
        profile.newsletter_frequency = "off"
        self.assertTrue(cm_sync.sync_profile(profile, client=client))
        self.assertEqual(client.calls, [])

    def test_new_members_get_the_weekly_newsletter_by_default(self):
        client = FakeClient()
        profile = make_user().profile
        self.assertTrue(cm_sync.sync_profile(profile, client=client))
        (call,) = [c for c in client.calls if c[0] == "upsert"]
        self.assertEqual(call[1][0], "newsletter-list")
        self.assertEqual(call[1][3], {cm_sync.NEWSLETTER_FIELD: "weekly"})

    def test_a_routine_sync_never_resubscribes_but_saving_settings_does(self):
        client = FakeClient()
        profile = make_user().profile
        cm_sync.sync_profile(profile, client=client)
        profile.user.first_name = "Renamed"  # changes the state, so it syncs again
        cm_sync.sync_profile(profile, client=client)
        self.assertEqual([c[2]["resubscribe"] for c in client.calls if c[0] == "upsert"],
                         [False, False])
        profile.user.first_name = "Again"
        profile.cm_resubscribe = {"newsletter"}
        cm_sync.sync_profile(profile, client=client)
        upserts = [c for c in client.calls if c[0] == "upsert"]
        self.assertIs(upserts[-1][2]["resubscribe"], True)

    def test_nothing_is_pushed_until_the_lists_are_set_up(self):
        client = FakeClient()
        profile = make_user().profile
        with override_settings(CM_NEWSLETTER_LIST_ID=""):
            self.assertFalse(cm_sync.sync_profile(profile, client=client))
        self.assertEqual(client.calls, [])
        self.assertEqual(profile.cm_synced_state, "")

    def test_clearing_alerts_unsubscribes_from_the_alert_list(self):
        client = FakeClient()
        profile = make_user(topics=["Migration"]).profile
        cm_sync.sync_profile(profile, client=client)
        profile.alert_topics = []
        cm_sync.sync_profile(profile, client=client)
        self.assertIn(("unsubscribe", ("alert-list", profile.user.email), {}), client.calls)

    def test_deactivated_user_is_unsubscribed_everywhere(self):
        client = FakeClient()
        profile = make_user(topics=["Migration"]).profile
        cm_sync.sync_profile(profile, client=client)
        profile.user.is_active = False
        cm_sync.sync_profile(profile, client=client)
        unsubscribed = {c[1][0] for c in client.calls if c[0] == "unsubscribe"}
        self.assertEqual(unsubscribed, {"newsletter-list", "alert-list"})

    def test_changed_email_unsubscribes_the_old_address(self):
        client = FakeClient()
        profile = make_user(topics=["Migration"]).profile
        old = profile.user.email
        cm_sync.sync_profile(profile, client=client)
        profile.user.email = "new@example.com"
        cm_sync.sync_profile(profile, client=client)
        self.assertIn(("unsubscribe", ("alert-list", old), {}), client.calls)
        self.assertIn("upsert", client.names())

    def test_cm_failure_never_raises_and_is_retried(self):
        client = FakeClient()
        client.fail = True
        profile = make_user(topics=["Migration"]).profile
        self.assertFalse(cm_sync.sync_profile(profile, client=client))
        self.assertEqual(profile.cm_synced_state, "")
        client.fail = False
        self.assertTrue(cm_sync.sync_profile(profile, client=client))

    def test_saving_preferences_queues_a_sync(self):
        user = make_user()
        with mock.patch("accounts.cm_sync.sync_profile") as sync, \
                self.captureOnCommitCallbacks(execute=True):
            profile = Profile.objects.get(pk=user.profile.pk)
            profile.alert_topics = ["Migration"]
            profile.save()
        sync.assert_called_once()

    @override_settings(CAMPAIGN_DELIVERY="smtp")
    def test_nothing_happens_without_cm_settings(self):
        with mock.patch("accounts.cm_sync.sync_profile") as sync, \
                self.captureOnCommitCallbacks(execute=True):
            make_user(topics=["Migration"])
        sync.assert_not_called()


@override_settings(**CM)
class WebhookTests(TestCase):
    def _post(self, secret="s3cret", list_id="alert-list", email="w@example.com", kind="Deactivate"):
        body = {"ListID": list_id, "Events": [{"Type": kind, "EmailAddress": email}]}
        return self.client.post(reverse("cm_webhook", kwargs={"secret": secret}),
                                json.dumps(body), content_type="application/json")

    def test_wrong_secret_is_404(self):
        self.assertEqual(self._post(secret="nope").status_code, 404)

    def test_unsubscribe_from_alerts_clears_alert_preferences(self):
        user = make_user("w@example.com", topics=["Migration"], countries=["US"], universities=[1])
        self.assertEqual(self._post().status_code, 204)
        profile = Profile.objects.get(user=user)
        self.assertEqual((profile.alert_topics, profile.alert_countries, profile.alert_universities), ([], [], []))

    def test_unsubscribe_from_the_newsletter_turns_it_off_but_keeps_alerts(self):
        user = make_user("w@example.com", topics=["Migration"])
        Profile.objects.filter(user=user).update(newsletter_frequency="weekly")
        self._post(list_id="newsletter-list")
        profile = Profile.objects.get(user=user)
        self.assertEqual(profile.newsletter_frequency, "off")
        self.assertEqual(profile.alert_topics, ["Migration"])

    def test_does_not_echo_back_to_cm(self):
        make_user("w@example.com", topics=["Migration"])
        with mock.patch("accounts.cm_sync.sync_profile") as sync, \
                self.captureOnCommitCallbacks(execute=True):
            self._post()
        sync.assert_not_called()

    def test_unknown_email_and_other_events_are_ignored(self):
        user = make_user("w@example.com", topics=["Migration"])
        self.assertEqual(self._post(email="ghost@example.com").status_code, 204)
        self._post(kind="Subscribe")
        self.assertEqual(Profile.objects.get(user=user).alert_topics, ["Migration"])

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(reverse("cm_webhook", kwargs={"secret": "s3cret"})).status_code, 405)


@override_settings(**CM)
class NewsletterCampaignTests(TestCase):
    def setUp(self):
        SpecialIssue.objects.create(
            journal="J", title="Open call", status="approved",
            submission_deadline=timezone.localdate() + timedelta(days=5))

    def test_sends_one_campaign_to_the_weekly_segment(self):
        client = FakeClient()
        campaign = campaigns.send_newsletter_campaign(["weekly"], client=client)
        self.assertEqual(campaign.status, "sent")
        create = next(c for c in client.calls if c[0] == "create_campaign")[2]
        self.assertEqual(create["segment_ids"], ["seg-weekly"])
        self.assertIn("<unsubscribe", campaign.html)
        self.assertIn("Open call", campaign.html)
        self.assertNotIn("cid:", campaign.html)

    def test_the_monthly_cohort_is_added_in_one_campaign(self):
        client = FakeClient()
        campaigns.send_newsletter_campaign(["weekly", "monthly"], client=client)
        self.assertEqual(client.names().count("create_campaign"), 1)
        create = next(c for c in client.calls if c[0] == "create_campaign")[2]
        self.assertEqual(create["segment_ids"], ["seg-weekly", "seg-monthly"])

    def test_monthly_cohort_only_in_the_first_seven_days_of_the_month(self):
        tz = timezone.get_current_timezone()
        first = timezone.datetime(2026, 11, 2, 12, tzinfo=tz)
        later = timezone.datetime(2026, 11, 9, 12, tzinfo=tz)
        self.assertEqual(campaigns.newsletter_cohorts(first), ["weekly", "monthly"])
        self.assertEqual(campaigns.newsletter_cohorts(later), ["weekly"])

    def test_a_week_with_nothing_to_list_sends_nothing(self):
        SpecialIssue.objects.all().delete()
        client = FakeClient()
        self.assertIsNone(campaigns.send_newsletter_campaign(["weekly"], client=client))
        self.assertEqual(client.calls, [])
        self.assertEqual(EmailCampaign.objects.count(), 0)

    def test_a_missing_segment_says_to_run_cm_setup(self):
        client = FakeClient()
        client.newsletter_segments = []
        with self.assertRaisesMessage(RuntimeError, "cm_setup"):
            campaigns.send_newsletter_campaign(["weekly"], client=client)

    def test_failure_is_recorded_and_raised(self):
        client = FakeClient()

        def boom(**kwargs):
            raise CampaignMonitorError("nope", status=400)
        client.create_campaign = boom
        with self.assertRaises(CampaignMonitorError):
            campaigns.send_newsletter_campaign(["weekly"], client=client)
        self.assertEqual(EmailCampaign.objects.get().status, "failed")


@override_settings(**CM)
class AlertCampaignTests(TestCase):
    def setUp(self):
        self.recent = timezone.now() - timedelta(days=1)

    def test_only_followed_interests_get_segments_and_items(self):
        make_user("a@example.com", topics=["Migration"])
        make_publication("Migration paper", self.recent, topic=["Migration"])
        make_publication("Nobody follows this", self.recent, topic=["Gender"])
        client = FakeClient()
        campaign = campaigns.prepare_alerts(client=client)
        titles = [c[1][1] for c in client.calls if c[0] == "create_segment"]
        self.assertIn("Alert t-migration", titles)
        self.assertNotIn("Alert t-gender", titles)
        self.assertIn("Migration paper", campaign.html)
        self.assertNotIn("Nobody follows this", campaign.html)

    def test_each_item_is_wrapped_in_its_own_segments(self):
        make_user("a@example.com", topics=["Migration"])
        make_user("b@example.com", countries=["US"])
        make_publication("Migration paper", self.recent, topic=["Migration"])
        make_visit("Visitor", self.recent, countries=["US"])
        campaign = campaigns.prepare_alerts(client=FakeClient())
        self.assertIn('[ifmemberof:"Labor Hub Alerts|Alert t-migration"]', campaign.html)
        self.assertIn('[ifmemberof:"Labor Hub Alerts|Alert c-US"]', campaign.html)
        self.assertEqual(campaign.html.count("[endif]"), 2)
        self.assertIn("[ifmemberof:", campaign.text)

    def test_item_matching_two_interests_lists_both_segments(self):
        make_user("a@example.com", topics=["Migration"])
        make_user("b@example.com", topics=["Gender"])
        make_publication("Both", self.recent, topic=["Migration", "Gender"])
        campaign = campaigns.prepare_alerts(client=FakeClient())
        self.assertIn('"Labor Hub Alerts|Alert t-gender","Labor Hub Alerts|Alert t-migration"', campaign.html)

    def test_no_matches_means_no_campaign(self):
        make_user("a@example.com", topics=["Migration"])
        make_publication("Unrelated", self.recent, topic=["Gender"])
        client = FakeClient()
        self.assertIsNone(campaigns.prepare_alerts(client=client))
        self.assertEqual(EmailCampaign.objects.count(), 0)

    def test_recipient_segment_is_the_or_of_relevant_interests(self):
        make_user("a@example.com", topics=["Migration"], countries=["US"])
        make_publication("Migration paper", self.recent, topic=["Migration"])
        make_visit("Visitor", self.recent, countries=["US"])
        client = FakeClient()
        campaigns.prepare_alerts(client=client)
        recipients = next(c for c in client.calls
                          if c[0] == "create_segment" and c[1][1].startswith("Alert recipients"))
        (group,) = recipients[1][2]  # one rule group => the rules are ORed by CM
        self.assertEqual(
            sorted(group), [("[AlertCountries]", "CONTAINS |c:US|"), ("[AlertTopics]", "CONTAINS |t:migration|")])

    def test_previous_weeks_segments_are_cleaned_up(self):
        make_user("a@example.com", topics=["Migration"])
        make_publication("Migration paper", self.recent, topic=["Migration"])
        client = FakeClient()
        client.alert_segments = [{"Title": "Alert t-old", "SegmentID": "old-id"}]
        campaigns.prepare_alerts(client=client)
        self.assertIn(("delete_segment", ("old-id",), {}), client.calls)

    def test_inactive_members_do_not_make_an_interest_relevant(self):
        user = make_user("a@example.com", topics=["Migration"])
        CustomUser.objects.filter(pk=user.pk).update(is_active=False)
        make_publication("Migration paper", self.recent, topic=["Migration"])
        self.assertIsNone(campaigns.prepare_alerts(client=FakeClient()))

    def test_send_creates_the_campaign_once(self):
        make_user("a@example.com", topics=["Migration"])
        make_publication("Migration paper", self.recent, topic=["Migration"])
        client = FakeClient()
        campaigns.prepare_alerts(client=client)
        sent = campaigns.send_prepared_alerts(client=client)
        self.assertEqual(sent.status, "sent")
        create = next(c for c in client.calls if c[0] == "create_campaign")[2]
        self.assertEqual(len(create["segment_ids"]), 1)
        self.assertIsNone(campaigns.send_prepared_alerts(client=client))
        self.assertEqual(client.names().count("create_campaign"), 1)

    def test_next_week_starts_where_the_last_ended(self):
        make_user("a@example.com", topics=["Migration"])
        make_publication("Migration paper", self.recent, topic=["Migration"])
        client = FakeClient()
        campaigns.prepare_alerts(client=client)
        campaigns.send_prepared_alerts(client=client)
        self.assertIsNone(campaigns.prepare_alerts(client=client))


@override_settings(**CM)
class CommandAndSnapshotTests(TestCase):
    def test_snapshot_is_served_by_token_only(self):
        campaign = EmailCampaign.objects.create(
            kind="alerts", subject="s", html="<p>hi</p>", text="hi",
            period_start=timezone.now(), period_end=timezone.now())
        url = reverse("campaign_snapshot", kwargs={"token": campaign.token, "ext": "html"})
        response = self.client.get(url)
        self.assertContains(response, "<p>hi</p>")
        self.assertEqual(response["X-Robots-Tag"], "noindex")
        self.assertEqual(self.client.get(reverse(
            "campaign_snapshot", kwargs={"token": "guess", "ext": "html"})).status_code, 404)
        self.assertEqual(self.client.get(url.replace(".html", ".txt")).content, b"hi")

    def test_the_scheduled_newsletter_is_a_campaign_not_per_user_mail(self):
        make_user("a@example.com")
        SpecialIssue.objects.create(
            journal="J", title="Open call", status="approved",
            submission_deadline=timezone.localdate() + timedelta(days=5))
        fake = FakeClient()
        with mock.patch("core.management.commands.send_newsletter.CampaignMonitorClient",
                        return_value=fake):
            call_command("send_newsletter", "--scheduled", verbosity=0)
        self.assertEqual(mail.outbox, [])
        self.assertIn("create_campaign", fake.names())

    @override_settings(CM_NEWSLETTER_LIST_ID="")
    def test_the_scheduled_newsletter_is_a_noop_until_cm_is_set_up(self):
        call_command("send_newsletter", "--scheduled", verbosity=0)
        self.assertEqual(mail.outbox, [])

    def test_send_alerts_prepare_then_send(self):
        make_user("a@example.com", topics=["Migration"])
        make_publication("Migration paper", timezone.now() - timedelta(days=1), topic=["Migration"])
        fake = FakeClient()
        with mock.patch("accounts.campaigns.CampaignMonitorClient", return_value=fake):
            call_command("send_alerts", "--prepare")
            self.assertNotIn("create_campaign", fake.names())
            call_command("send_alerts")
        self.assertEqual(mail.outbox, [])
        self.assertIn("send_campaign", fake.names())

    @override_settings(CAMPAIGN_DELIVERY="smtp")
    def test_prepare_is_a_noop_without_cm_and_plain_run_still_mails(self):
        make_user("a@example.com", topics=["Migration"])
        make_publication("Migration paper", timezone.now() - timedelta(days=1), topic=["Migration"])
        call_command("send_alerts", "--prepare")
        self.assertEqual(mail.outbox, [])
        call_command("send_alerts")
        self.assertEqual(len(mail.outbox), 1)

    def test_cm_sync_command_backfills_then_is_idempotent(self):
        make_user("a@example.com", topics=["Migration"])
        fake = FakeClient()
        with mock.patch("accounts.cm_sync.CampaignMonitorClient", return_value=fake):
            call_command("cm_sync")
            calls = len(fake.calls)
            self.assertGreater(calls, 0)
            call_command("cm_sync")
        self.assertEqual(len(fake.calls), calls)
