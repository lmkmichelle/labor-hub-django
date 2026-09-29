"""One-off local command: send a real copy of every outgoing email template
to a single inbox, through whatever SMTP backend is currently configured
(see .env's EMAIL_HOST_PASSWORD/DEFAULT_FROM_EMAIL/etc.) -- for visually
reviewing the HTML design before a change goes anywhere near ``main``/prod.

    python manage.py send_test_emails --to you@cornell.edu
    python manage.py send_test_emails --to you@cornell.edu --only approved,digest

Every send here goes through the real ``send_*_email``/form/view code this
app actually uses in production -- nothing is re-implemented -- so what
lands in the inbox is exactly what a real user would receive. Some email
types need a real, saved database row to work at all (the staff alert reads
its recipients from the DB; the digest reads real approved content; the
password reset looks up a real active user). If ``--to`` isn't an existing
account, a throwaway one is created for the send and deleted again in a
``finally`` block. If ``--to`` *is* an existing account (e.g. your own dev
superuser), that real account is reused as-is instead -- never created,
never deleted, and any field this command needs to change temporarily
(digest subscription) is restored afterward.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import override_settings
from django.utils import timezone

from accounts.digests import send_user_digest
from accounts.emails import (
    send_advisor_review_email,
    send_application_approved_email,
    send_application_rejected_email,
    send_application_submitted_email,
)
from accounts.forms import LaborHubPasswordResetForm
from accounts.models import CustomUser, UserApplication
from core.models import ContactMessage
from core.views import _send_contact_notification
from publications.emails import send_paper_advisor_ack_email
from publications.models import Publication

ALL_KEYS = [
    "approved", "rejected", "staff_alert", "advisor_review",
    "paper_advisor_ack", "digest", "contact", "password_reset",
]


class Command(BaseCommand):
    help = "Send one real test copy of every outgoing email to --to, for visual review."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to", required=True, help="Address every test email is sent to.")
        parser.add_argument(
            "--only", default="",
            help="Comma-separated subset of: " + ", ".join(ALL_KEYS))

    def handle(self, *args, **options):
        to = options["to"]
        requested = [k.strip() for k in options["only"].split(",") if k.strip()]
        keys = requested or ALL_KEYS
        unknown = sorted(set(keys) - set(ALL_KEYS))
        if unknown:
            raise CommandError(
                f"Unknown --only value(s): {', '.join(unknown)}. "
                f"Choices are: {', '.join(ALL_KEYS)}"
            )

        for key in keys:
            self.stdout.write(f"Sending '{key}' to {to} ...")
            getattr(self, f"_send_{key}")(to)
            self.stdout.write(self.style.SUCCESS(f"  sent '{key}'"))

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
