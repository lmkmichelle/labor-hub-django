"""Campaign Monitor (CM) SMTP integration shared by every outgoing email.

CM's classic transactional SMTP endpoint groups and configures tracking for
each email via plain SMTP headers (no API client needed):
https://www.campaignmonitor.com/api/transactional/ -- "Assign groups for SMTP
sends" / "Advanced HTML email header options". These headers are inert on any
other SMTP server (the Upsun relay, Gmail, locmem in tests), so nothing here
is CM-specific enough to break local dev or the test suite.
"""
from email.mime.image import MIMEImage

from django.conf import settings
from django.contrib.staticfiles.finders import find as find_static
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend

GROUP_HEADER = "X-Cmail-GroupName"
TRACK_OPENS_HEADER = "X-Cmail-TrackOpens"
TRACK_CLICKS_HEADER = "X-Cmail-TrackClicks"

# Referenced from every email template as src="cid:labor_hub_logo".
LOGO_CID = "labor_hub_logo"


def cm_headers(track_opens=False, track_clicks=False):
    """Headers filing a message under the single Labor Hub group in CM's
    reporting (``settings.EMAIL_GROUP_NAME`` -- every outgoing email uses the
    same group, per admin request, rather than one group per email type).

    ``track_clicks`` defaults off: CM rewrites every link to a tracking
    redirect, which is undesirable for links like a password reset. Only the
    digest turns tracking on.
    """
    return {
        GROUP_HEADER: settings.EMAIL_GROUP_NAME,
        TRACK_OPENS_HEADER: "true" if track_opens else "false",
        TRACK_CLICKS_HEADER: "true" if track_clicks else "false",
    }


def default_reply_to():
    """The shared support mailbox (an EGA), or ``None`` until one is configured."""
    return [settings.REPLY_TO_EMAIL] if settings.REPLY_TO_EMAIL else None


def attach_logo(message):
    """Attach the site logo as an inline image every HTML email can show via
    ``<img src="cid:labor_hub_logo">``.

    Deliberately not a remote ``<img src="https://.../logo.png">``: most mail
    clients block remote images until the recipient explicitly allows them, so
    a link-only logo would render broken far more often than not -- which is
    exactly the "looks like a scam" impression a legitimate-looking email is
    trying to avoid. An inline (Content-ID) attachment always renders, with no
    round trip back to the site, and works the same in a local test send as
    in production regardless of whether the recipient can even reach the
    site's own URL.

    A no-op for a plain ``EmailMessage`` (nothing to attach an inline image
    to without an HTML part) and if the logo file can't be found, so a
    missing/misconfigured static file degrades to "no logo", never a broken
    send.
    """
    if not isinstance(message, EmailMultiAlternatives):
        return
    logo_path = find_static("images/logo_small.png")
    if not logo_path:
        return
    with open(logo_path, "rb") as logo_file:
        image = MIMEImage(logo_file.read())
    image.add_header("Content-ID", f"<{LOGO_CID}>")
    image.add_header("Content-Disposition", "inline", filename="logo_small.png")
    message.mixed_subtype = "related"
    message.attach(image)


class CampaignMonitorEmailBackend(SMTPEmailBackend):
    """SMTP backend that guarantees every message is grouped for CM reporting.

    Covers mail this app doesn't build itself -- Django's password reset view,
    ``mail_admins`` -- without subclassing those. A message that already set
    its own group (every function in accounts/publications/core ``emails.py``
    modules does) is left untouched.
    """

    def send_messages(self, email_messages):
        for message in email_messages:
            message.extra_headers.setdefault(GROUP_HEADER, settings.EMAIL_GROUP_NAME)
            message.extra_headers.setdefault(TRACK_CLICKS_HEADER, "false")
            message.extra_headers.setdefault(TRACK_OPENS_HEADER, "false")
        return super().send_messages(email_messages)
