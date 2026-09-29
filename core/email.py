"""Campaign Monitor (CM) SMTP integration shared by every outgoing email.

CM's classic transactional SMTP endpoint groups and configures tracking for
each email via plain SMTP headers (no API client needed):
https://www.campaignmonitor.com/api/transactional/ -- "Assign groups for SMTP
sends" / "Advanced HTML email header options". These headers are inert on any
other SMTP server (the Upsun relay, Gmail, locmem in tests), so nothing here
is CM-specific enough to break local dev or the test suite.
"""
from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend

GROUP_HEADER = "X-Cmail-GroupName"
TRACK_OPENS_HEADER = "X-Cmail-TrackOpens"
TRACK_CLICKS_HEADER = "X-Cmail-TrackClicks"


def cm_headers(group, track_opens=False, track_clicks=False):
    """Headers that file a message under ``group`` in CM's reporting.

    ``track_clicks`` defaults off: CM rewrites every link to a tracking
    redirect, which is undesirable for links like a password reset. Only the
    digest turns tracking on.
    """
    return {
        GROUP_HEADER: "{} - {}".format(settings.EMAIL_GROUP_PREFIX, group),
        TRACK_OPENS_HEADER: "true" if track_opens else "false",
        TRACK_CLICKS_HEADER: "true" if track_clicks else "false",
    }


def default_reply_to():
    """The shared support mailbox (an EGA), or ``None`` until one is configured."""
    return [settings.REPLY_TO_EMAIL] if settings.REPLY_TO_EMAIL else None


class CampaignMonitorEmailBackend(SMTPEmailBackend):
    """SMTP backend that guarantees every message is grouped for CM reporting.

    Covers mail this app doesn't build itself -- Django's password reset view,
    ``mail_admins`` -- without subclassing those. A message that already set
    its own group (every function in accounts/publications/core ``emails.py``
    modules does) is left untouched.
    """

    def send_messages(self, email_messages):
        for message in email_messages:
            message.extra_headers.setdefault(
                GROUP_HEADER, "{} - Other".format(settings.EMAIL_GROUP_PREFIX)
            )
            message.extra_headers.setdefault(TRACK_CLICKS_HEADER, "false")
            message.extra_headers.setdefault(TRACK_OPENS_HEADER, "false")
        return super().send_messages(email_messages)
