"""Nudge advisors who haven't acted on a student's application.

Run daily. For each pending student application that names an advisor:

* 3 days old  -> first reminder to the advisor
* 7 days old  -> second reminder
* 14 days old -> the admins' shared inbox is told, so an administrator can step in

Each step happens once (counted on the application), so re-running is safe.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.emails import send_advisor_review_email, send_application_submitted_email
from accounts.models import CustomUser, UserApplication

REMINDER_AFTER = (timedelta(days=3), timedelta(days=7))
ESCALATE_AFTER = timedelta(days=14)


class Command(BaseCommand):
    help = "Remind student advisors of pending applications; escalate to admins after 14 days."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        now = timezone.now()
        pending = UserApplication.objects.filter(
            status=UserApplication.Status.PENDING, role=CustomUser.Role.STUDENT,
            advisor__isnull=False,
        ).select_related("advisor")
        reminded = escalated = 0
        for app in pending:
            age = now - app.applied_at
            if age >= ESCALATE_AFTER:
                if app.advisor_escalated_at is None:
                    self.stdout.write(f"{'[dry-run] ' if dry else ''}escalate: {app.email}")
                    if not dry:
                        send_application_submitted_email(app, unanswered_advisor=True)
                        app.advisor_escalated_at = now
                        app.save(update_fields=["advisor_escalated_at"])
                    escalated += 1
            elif app.advisor_reminders_sent < len(REMINDER_AFTER) and \
                    age >= REMINDER_AFTER[app.advisor_reminders_sent]:
                self.stdout.write(f"{'[dry-run] ' if dry else ''}remind {app.advisor.email}: {app.email}")
                if not dry:
                    send_advisor_review_email(app, reminder=True)
                    app.advisor_reminders_sent += 1
                    app.save(update_fields=["advisor_reminders_sent"])
                reminded += 1
        self.stdout.write(self.style.SUCCESS(
            f"{'[dry-run] ' if dry else ''}{reminded} reminded, {escalated} escalated."))
