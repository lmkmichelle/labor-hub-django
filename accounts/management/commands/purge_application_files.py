"""Delete the files uploaded with applications once they have served their purpose.

* Approved: the research samples are deleted (``UserApplication.approve`` already does
  this; this run backfills older approvals and retries failures). The resume stays, as
  it became the member's profile CV.
* Rejected: the research samples and the resume are deleted 30 days after the rejection.
* Pending: never touched.

The application record itself (name, email, answers) is kept. Run daily from the
``application-files`` cron in ``.upsun/config.yaml``; ``--dry-run`` only reports.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from accounts.models import REJECTED_FILE_RETENTION, UserApplication


class Command(BaseCommand):
    help = "Delete application samples (approved) and samples + resume 30 days after rejection."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would be deleted without deleting anything.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        cutoff = timezone.now() - REJECTED_FILE_RETENTION
        pending_files = UserApplication.objects.filter(files_purged_at__isnull=True)

        approved = pending_files.filter(
            status=UserApplication.Status.APPROVED, research_papers__isnull=False).distinct()
        rejected = pending_files.filter(
            status=UserApplication.Status.REJECTED, reviewed_at__lt=cutoff
        ).filter(Q(research_papers__isnull=False) | Q(resume__gt="")).distinct()

        counts = {}
        for label, queryset, include_resume in (
                ("approved", approved, False), ("rejected", rejected, True)):
            done = 0
            for application in queryset:
                if dry or application.delete_files(include_resume=include_resume):
                    done += 1
            counts[label] = done
        verb = "would clean" if dry else "cleaned"
        self.stdout.write(
            f"purge_application_files: {verb} {counts['approved']} approved and "
            f"{counts['rejected']} rejected application(s).")
