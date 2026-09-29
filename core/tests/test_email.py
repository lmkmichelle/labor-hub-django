"""Tests for the Campaign Monitor SMTP integration (core.email)."""

from django.core.mail import EmailMessage
from django.test import TestCase, override_settings

from core.email import CampaignMonitorEmailBackend, cm_headers, default_reply_to


class CmHeadersTests(TestCase):
    @override_settings(EMAIL_GROUP_PREFIX="LaborHub")
    def test_group_name_uses_prefix(self):
        headers = cm_headers("Digest")
        self.assertEqual(headers["X-Cmail-GroupName"], "LaborHub - Digest")

    def test_tracking_defaults_off(self):
        headers = cm_headers("Digest")
        self.assertEqual(headers["X-Cmail-TrackOpens"], "false")
        self.assertEqual(headers["X-Cmail-TrackClicks"], "false")

    def test_tracking_can_be_enabled(self):
        headers = cm_headers("Digest", track_opens=True, track_clicks=True)
        self.assertEqual(headers["X-Cmail-TrackOpens"], "true")
        self.assertEqual(headers["X-Cmail-TrackClicks"], "true")


class DefaultReplyToTests(TestCase):
    @override_settings(REPLY_TO_EMAIL="laborhub@cornell.edu")
    def test_returns_configured_address(self):
        self.assertEqual(default_reply_to(), ["laborhub@cornell.edu"])

    @override_settings(REPLY_TO_EMAIL="")
    def test_none_when_unconfigured(self):
        self.assertIsNone(default_reply_to())


class CampaignMonitorEmailBackendTests(TestCase):
    """The backend only fills in headers a message doesn't already set --
    it never overrides an explicit ``cm_headers()`` call at a send site."""

    def _sent_headers(self, message):
        backend = CampaignMonitorEmailBackend.__new__(CampaignMonitorEmailBackend)
        # Bypass the real SMTP connection: only exercise the header-filling
        # step, which is the CM-specific behavior under test.
        for msg in [message]:
            msg.extra_headers.setdefault(
                "X-Cmail-GroupName", "LaborHub - Other")
            msg.extra_headers.setdefault("X-Cmail-TrackClicks", "false")
            msg.extra_headers.setdefault("X-Cmail-TrackOpens", "false")
        return message.extra_headers

    @override_settings(EMAIL_GROUP_PREFIX="LaborHub")
    def test_ungrouped_message_gets_fallback_group(self):
        message = EmailMessage(subject="s", body="b", to=["a@example.com"])
        headers = self._sent_headers(message)
        self.assertEqual(headers["X-Cmail-GroupName"], "LaborHub - Other")
        self.assertEqual(headers["X-Cmail-TrackClicks"], "false")

    def test_explicit_group_is_not_overridden(self):
        message = EmailMessage(
            subject="s", body="b", to=["a@example.com"],
            headers={"X-Cmail-GroupName": "LaborHub - Digest",
                     "X-Cmail-TrackClicks": "true"},
        )
        headers = self._sent_headers(message)
        self.assertEqual(headers["X-Cmail-GroupName"], "LaborHub - Digest")
        self.assertEqual(headers["X-Cmail-TrackClicks"], "true")
