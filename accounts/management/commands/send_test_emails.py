"""One-off local command: send a real copy of every outgoing email template
to a single inbox, through whatever SMTP backend is currently configured
(see .env's EMAIL_HOST_PASSWORD/DEFAULT_FROM_EMAIL/etc.) -- for visually
reviewing the HTML design before a change goes anywhere near ``main``/prod.

    python manage.py send_test_emails --to you@cornell.edu
    python manage.py send_test_emails --to you@cornell.edu --only approved,digest

Or, to review the HTML without sending anything anywhere (no SMTP
credentials needed, nothing leaves the machine):

    python manage.py send_test_emails --preview
    open /tmp/labor-hub-email-previews/index.html

Every send here goes through the real ``send_*_email``/form/view code this
app actually uses in production -- nothing is re-implemented -- so what
lands in the inbox (or the preview file) is exactly what a real user would
receive. Some email types need a real, saved database row to work at all
(the staff alert reads its recipients from the DB; the digest reads real
approved content; the password reset looks up a real active user). If
``--to`` isn't an existing account, a throwaway one is created for the send
and deleted again in a ``finally`` block. If ``--to`` *is* an existing
account (e.g. your own dev superuser), that real account is reused as-is
instead -- never created, never deleted, and any field this command needs
to change temporarily (digest subscription) is restored afterward.
"""
import base64
import os
import tempfile

from django.conf import settings
from django.core import mail
from django.core.management.base import BaseCommand, CommandError
from django.test import override_settings
from django.utils import timezone
from django.utils.html import escape

from accounts.alerts import send_user_alerts
from accounts.digests import send_user_digest
from accounts.emails import (
    send_advisor_review_email,
    send_application_approved_email,
    send_application_rejected_email,
    send_application_submitted_email,
)
from accounts.forms import LaborHubPasswordResetForm
from accounts.models import CustomUser, UserApplication
from core.email import LOGO_CID
from core.models import ContactMessage
from core.views import _send_contact_confirmation, _send_contact_notification
from publications.emails import send_paper_advisor_ack_email
from publications.models import Publication
from seminars.models import Seminar

ALL_KEYS = [
    "approved", "rejected", "staff_alert", "advisor_review",
    "paper_advisor_ack", "digest", "alerts", "contact", "contact_confirmation",
    "password_reset",
]

# Matches core.constants.RECOMMENDED_KEYWORDS[0] -- any entry works, this is
# just a fixed one so the preview publication's topic has something to match.
PREVIEW_ALERT_TOPIC = "Education and Human Capital"
PREVIEW_ALERT_COUNTRY = "US"

PREVIEW_DEFAULT_TO = "preview@example.com"
PREVIEW_DEFAULT_DIR = os.path.join(tempfile.gettempdir(), "labor-hub-email-previews")


class Command(BaseCommand):
    help = "Send one real test copy of every outgoing email to --to, for visual review."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to", default=None,
            help="Address every test email is sent to. Defaults to "
                 f"{PREVIEW_DEFAULT_TO} when --preview is used.")
        parser.add_argument(
            "--only", default="",
            help="Comma-separated subset of: " + ", ".join(ALL_KEYS))
        parser.add_argument(
            "--preview", action="store_true",
            help="Render each email to a local HTML file instead of sending "
                 "it anywhere -- no SMTP backend/credentials needed.")
        parser.add_argument(
            "--out", default=PREVIEW_DEFAULT_DIR,
            help=f"Directory to write previews into (--preview only). "
                 f"Default: {PREVIEW_DEFAULT_DIR}")

    def handle(self, *args, **options):
        preview = options["preview"]
        to = options["to"] or (PREVIEW_DEFAULT_TO if preview else None)
        if not to:
            raise CommandError("--to is required unless --preview is used.")
        requested = [k.strip() for k in options["only"].split(",") if k.strip()]
        keys = requested or ALL_KEYS
        unknown = sorted(set(keys) - set(ALL_KEYS))
        if unknown:
            raise CommandError(
                f"Unknown --only value(s): {', '.join(unknown)}. "
                f"Choices are: {', '.join(ALL_KEYS)}"
            )

        if preview:
            self._preview(keys, to, options["out"])
            return

        for key in keys:
            self.stdout.write(f"Sending '{key}' to {to} ...")
            getattr(self, f"_send_{key}")(to)
            self.stdout.write(self.style.SUCCESS(f"  sent '{key}'"))

    def _preview(self, keys, to, out_dir):
        """Render each requested email's HTML alternative to a local file,
        using the locmem backend so nothing is actually sent -- the exact
        send code path still runs (fixture rows, subjects, headers), only
        the transport is swapped. The inline CID logo is inlined further,
        as a base64 data URI, so the file renders correctly with no mail
        client and no static file server involved -- just opening it in a
        browser.
        """
        os.makedirs(out_dir, exist_ok=True)
        index_rows = []
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            for key in keys:
                mail.outbox = []
                self.stdout.write(f"Rendering '{key}' ...")
                getattr(self, f"_send_{key}")(to)
                if not mail.outbox:
                    self.stdout.write(self.style.WARNING(
                        f"  '{key}': nothing was sent, skipping"))
                    continue
                for i, message in enumerate(mail.outbox):
                    suffix = "" if len(mail.outbox) == 1 else f"_{i}"
                    filename = f"{key}{suffix}.html"
                    html = self._inline_preview_html(message)
                    with open(os.path.join(out_dir, filename), "w") as f:
                        f.write(html)
                    index_rows.append((filename, message.subject))
                    self.stdout.write(self.style.SUCCESS(f"  wrote {filename}"))
            # The locmem backend is only used to capture each message in
            # memory long enough to render it to a file -- nothing was
            # actually sent, so leave no trace in mail.outbox for a caller
            # (e.g. a test) that runs this in preview mode.
            mail.outbox = []

        index_path = os.path.join(out_dir, "index.html")
        with open(index_path, "w") as f:
            f.write(self._index_html(index_rows))
        self.stdout.write(self.style.SUCCESS(f"\nOpen {index_path}"))

    def _inline_preview_html(self, message):
        html = next(
            (content for content, mimetype in getattr(message, "alternatives", [])
             if mimetype == "text/html"),
            None,
        )
        if html is None:
            # Plain-text-only message: still produce something viewable.
            return f"<pre>{escape(message.body)}</pre>"
        for attachment in message.attachments:
            if attachment.get("Content-ID") == f"<{LOGO_CID}>":
                data = attachment.get_payload(decode=True)
                content_type = attachment.get_content_type() or "image/png"
                data_uri = f"data:{content_type};base64,{base64.b64encode(data).decode()}"
                html = html.replace(f"cid:{LOGO_CID}", data_uri)
                break
        return html

    def _index_html(self, rows):
        items = "\n".join(
            f'<li><a href="{filename}">{escape(filename)}</a> &mdash; {escape(subject)}</li>'
            for filename, subject in rows
        )
        return (
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            "<title>Labor Hub email previews</title></head><body>"
            f"<h1>Labor Hub email previews</h1><ul>{items}</ul>"
            "</body></html>"
        )

    def _get_or_reuse_user(self, to, **create_fields):
        """A real account matching ``to`` is reused untouched; only when
        none exists is a throwaway one created (for the caller to delete
        afterward). Returns ``(user, created)``."""
        existing = CustomUser.objects.filter(email=to).first()
        if existing:
            return existing, False
        defaults = {
            "password": "x", "first_name": "Test", "last_name": "Tester",
            "is_active": True,
        }
        defaults.update(create_fields)
        return CustomUser.objects.create_user(email=to, **defaults), True

    # Each of these mirrors the real call site as closely as possible --
    # see the docstring above for why some create/delete real DB rows.

    def _send_approved(self, to):
        user = CustomUser(email=to, first_name="Test", last_name="User")
        send_application_approved_email(user, fail_silently=False)

    def _send_rejected(self, to):
        application = UserApplication(email=to, first_name="Test", last_name="User")
        send_application_rejected_email(application, fail_silently=False)

    def _send_staff_alert(self, to):
        # send_application_submitted_email reads its recipients from
        # CustomUser.objects.filter(is_staff=True, is_active=True) and
        # builds review_url from application.pk -- both need real, saved rows.
        staff, created = self._get_or_reuse_user(
            to, role=CustomUser.Role.ADMIN, is_staff=True)
        if not created and not (staff.is_staff and staff.is_active):
            raise CommandError(
                f"{to} is an existing account but isn't an active staff "
                "member, so it wouldn't actually receive this email -- "
                "can't preview it without creating a duplicate account."
            )
        application = UserApplication.objects.create(
            email="applicant-preview@example.com", first_name="Preview",
            last_name="Applicant", position="Postdoc", department="Economics",
        )
        try:
            send_application_submitted_email(application, fail_silently=False)
        finally:
            application.delete()
            if created:
                staff.delete()

    def _send_advisor_review(self, to):
        advisor = CustomUser(
            email=to, first_name="Advisor", last_name="Test",
            role=CustomUser.Role.RESEARCHER,
        )
        application = UserApplication(
            email="student-preview@example.com", first_name="Preview",
            last_name="Student", role=CustomUser.Role.STUDENT, advisor=advisor,
        )
        send_advisor_review_email(application, fail_silently=False)

    def _send_paper_advisor_ack(self, to):
        advisor = CustomUser(email=to, first_name="Advisor", last_name="Test")
        submitter = CustomUser(
            email="submitter-preview@example.com", first_name="Sam",
            last_name="Submitter",
        )
        publication = Publication(
            title="A Preview Job Market Paper", is_job_market=True,
            jm_advisor=advisor, submitted_by=submitter,
        )
        send_paper_advisor_ack_email(publication, fail_silently=False)

    def _send_digest(self, to):
        # collect_new_content queries real approved rows, and send_user_digest
        # needs a saved user with a subscribed profile.
        user, created = self._get_or_reuse_user(to)
        original_frequency = user.profile.digest_frequency
        original_last_sent = user.profile.last_digest_sent_at
        user.profile.digest_frequency = user.profile.DigestFrequency.WEEKLY
        user.profile.last_digest_sent_at = None
        user.profile.save()
        publication = Publication.objects.create(
            title="A Preview Discussion Paper",
            abstract="A preview row for send_test_emails; deleted immediately after.",
            status="approved",
        )
        try:
            sent = send_user_digest(user, now=timezone.now())
            if not sent:
                self.stdout.write(self.style.WARNING(
                    "  digest: send_user_digest reported nothing to send"))
        finally:
            publication.delete()
            if created:
                user.delete()
            else:
                user.profile.digest_frequency = original_frequency
                user.profile.last_digest_sent_at = original_last_sent
                user.profile.save()

    def _send_alerts(self, to):
        # Mirrors _send_digest: collect_alert_matches queries real approved
        # rows, and send_user_alerts needs a saved user subscribed to the
        # topic/country the preview rows below match.
        user, created = self._get_or_reuse_user(to)
        original_topics = user.profile.alert_topics
        original_countries = user.profile.alert_countries
        original_last_sent = user.profile.last_alert_sent_at
        user.profile.alert_topics = [PREVIEW_ALERT_TOPIC]
        user.profile.alert_countries = [PREVIEW_ALERT_COUNTRY]
        user.profile.last_alert_sent_at = None
        user.profile.save()
        publication = Publication.objects.create(
            title="A Preview Discussion Paper",
            abstract="A preview row for send_test_emails; deleted immediately after.",
            status="approved",
            topic=[PREVIEW_ALERT_TOPIC],
        )
        visit = Seminar.objects.create(
            visitor_name="Preview Visitor",
            university_name="Preview University",
            status="approved",
            countries=[PREVIEW_ALERT_COUNTRY],
        )
        try:
            sent = send_user_alerts(user, now=timezone.now())
            if not sent:
                self.stdout.write(self.style.WARNING(
                    "  alerts: send_user_alerts reported nothing to send"))
        finally:
            publication.delete()
            visit.delete()
            if created:
                user.delete()
            else:
                user.profile.alert_topics = original_topics
                user.profile.alert_countries = original_countries
                user.profile.last_alert_sent_at = original_last_sent
                user.profile.save()

    def _send_contact(self, to):
        # _send_contact_notification always sends to settings.CONTACT_EMAIL,
        # not to the submitter -- override it for the duration of this send.
        message = ContactMessage(
            name="Preview Sender", email="sender-preview@example.com",
            message="This is a preview of the contact form notification email.",
            created_at=timezone.now(),
        )
        with override_settings(CONTACT_EMAIL=to):
            _send_contact_notification(message)

    def _send_contact_confirmation(self, to):
        message = ContactMessage(
            name="Preview Sender", email=to,
            message="This is a preview of the contact form confirmation email.",
            created_at=timezone.now(),
        )
        _send_contact_confirmation(message)

    def _send_password_reset(self, to):
        # Django's PasswordResetForm only emails an address with a real,
        # active account.
        user, created = self._get_or_reuse_user(to)
        try:
            form = LaborHubPasswordResetForm(data={"email": to})
            if not form.is_valid():
                raise CommandError(f"Password reset form invalid: {form.errors}")
            site_url = settings.SITE_URL.rstrip("/")
            domain = site_url.split("://", 1)[-1]
            form.save(
                domain_override=domain,
                use_https=site_url.startswith("https://"),
                email_template_name="registration/password_reset_email.txt",
                subject_template_name="registration/password_reset_subject.txt",
                html_email_template_name="registration/password_reset_email.html",
                extra_email_context={"site_url": site_url},
            )
        finally:
            if created:
                user.delete()
