from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from accounts.models import CustomUser, Profile
from accounts.tests.test_alerts import make_user


@override_settings(CM_API_KEY="k", CM_CLIENT_ID="c", CM_MEMBERS_LIST_ID="members",
                   CM_DIGEST_LIST_ID="", CM_ALERT_LIST_ID="", CAMPAIGN_DELIVERY="smtp")
class MembersOnlyTests(TestCase):
    def test_sync_fills_only_the_members_list_with_active_members(self):
        active = make_user(email="a@example.com")
        gone = make_user(email="b@example.com")
        CustomUser.objects.filter(pk=gone.pk).update(is_active=False)
        with mock.patch("accounts.management.commands.cm_sync.CampaignMonitorClient") as cls:
            call_command("cm_sync", "--members-only", verbosity=0)
        calls = cls.return_value.upsert_subscriber.call_args_list
        self.assertEqual([c.args[:2] for c in calls], [("members", "a@example.com")])
        self.assertIs(calls[0].kwargs["resubscribe"], False)
        cls.return_value.unsubscribe.assert_not_called()
        self.assertTrue(Profile.objects.filter(user=active).exists())

    def test_dry_run_calls_nothing(self):
        make_user(email="a@example.com")
        with mock.patch("accounts.management.commands.cm_sync.CampaignMonitorClient") as cls:
            call_command("cm_sync", "--members-only", "--dry-run", verbosity=0)
        cls.return_value.upsert_subscriber.assert_not_called()

    def test_needs_the_members_list_id(self):
        with override_settings(CM_MEMBERS_LIST_ID=""):
            with self.assertRaises(Exception):
                call_command("cm_sync", "--members-only", verbosity=0)

    def test_setup_creates_only_the_members_list(self):
        with mock.patch("accounts.management.commands.cm_setup.CampaignMonitorClient") as cls:
            client = cls.return_value
            client.lists.return_value = []
            client.create_list.return_value = "new-members-id"
            client.custom_fields.return_value = []
            call_command("cm_setup", "--members-only", verbosity=0)
        client.create_list.assert_called_once_with("Labor Hub Members")
        client.create_segment.assert_not_called()
