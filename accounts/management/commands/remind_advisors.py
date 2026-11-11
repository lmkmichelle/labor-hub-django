"""Nudge advisors who haven't acted on a student's application or a job market paper.

Run daily. For each pending student application that names an advisor:

* 3 days old  -> first reminder to the advisor
* 7 days old  -> second reminder
* 14 days old -> the admins' shared inbox is told, so an administrator can step in

Also, once the application is 7 days old the student is told it is still waiting on
their advisor.

Also, a pending job market paper whose advisor hasn't responded after 7 days gets one
reminder to that advisor.

Each step happens once (counted on the application), so re-running is safe.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.emails import (
    send_advisor_review_email, send_application_submitted_email,
    send_student_awaiting_advisor_email,
)
from accounts.models import CustomUser, UserApplication
from core.models import ApprovalStatus
from publications.emails import send_paper_advisor_ack_email
from publications.models import Publication

REMINDER_AFTER = (timedelta(days=3), timedelta(days=7))
ESCALATE_AFTER = timedelta(days=14)
STUDENT_REMINDER_AFTER = timedelta(days=7)
PAPER_REMINDER_AFTER = timedelta(days=7)


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
        reminded = escalated = students = 0
        for app in pending:
            age = now - app.applied_at
            if age >= STUDENT_REMINDER_AFTER and app.student_reminded_at is None:
                self.stdout.write(f"{'[dry-run] ' if dry else ''}tell student {app.email}")
                if not dry:
                    send_student_awaiting_advisor_email(app)
                    app.student_reminded_at = now
                    app.save(update_fields=["student_reminded_at"])
                students += 1
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
        papers = Publication.objects.filter(
            status=ApprovalStatus.PENDING, is_job_market=True, jm_advisor__isnull=False,
            jm_advisor_acknowledged__isnull=True, jm_advisor_reminded_at__isnull=True,
            applied_at__lte=now - PAPER_REMINDER_AFTER,
        ).select_related("jm_advisor", "submitted_by")
        paper_reminders = 0
        for paper in papers:
            self.stdout.write(f"{'[dry-run] ' if dry else ''}remind {paper.jm_advisor.email}: {paper.title}")
            if not dry:
                send_paper_advisor_ack_email(paper, reminder=True)
                paper.jm_advisor_reminded_at = now
                paper.save(update_fields=["jm_advisor_reminded_at"])
            paper_reminders += 1
        self.stdout.write(self.style.SUCCESS(
            f"{'[dry-run] ' if dry else ''}{reminded} advisors reminded, {students} students told, "
            f"{escalated} escalated, {paper_reminders} paper advisors reminded."))
