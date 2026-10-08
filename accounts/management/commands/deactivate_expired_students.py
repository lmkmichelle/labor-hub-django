"""Deactivate student accounts two years after they were created.

Students can use every resource on the site without an account, so there is
little reason to keep one open longer. A warning email goes out 30 days before
(once per student), then the account is deactivated. Nothing is deleted: the
student's papers and posts stay up, and the account can be reactivated if they
later apply as a fellow with the same email (see UserApplication.approve).

Run daily from the ``student-lifecycle`` cron in ``.upsun/config.yaml``.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.emails import send_student_deactivation_warning
from accounts.models import CustomUser

LIFETIME = timedelta(days=730)
WARNING_LEAD = timedelta(days=30)


class Command(BaseCommand):
    help = "Warn students 30 days before, then deactivate them 2 years after joining."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would happen without emailing or deactivating anyone.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()
        students = CustomUser.objects.filter(
            role=CustomUser.Role.STUDENT, is_active=True,
        ).select_related("profile")

        deactivated = warned = 0
        for user in students:
            expires = user.date_joined + LIFETIME
            if expires <= now:
                self.stdout.write(f"{'[dry-run] would deactivate' if dry_run else 'deactivate'}: {user.email}")
                if not dry_run:
                    user.is_active = False
                    user.save(update_fields=["is_active"])
                deactivated += 1
            elif expires - WARNING_LEAD <= now and not user.profile.deactivation_warned_at:
                self.stdout.write(f"{'[dry-run] would warn' if dry_run else 'warn'}: {user.email} (closes {expires:%Y-%m-%d})")
                if not dry_run:
                    if send_student_deactivation_warning(user, expires):
                        user.profile.deactivation_warned_at = now
                        user.profile.save(update_fields=["deactivation_warned_at"])
                warned += 1

        self.stdout.write(self.style.SUCCESS(
            f"{'[dry-run] ' if dry_run else ''}{warned} warned, {deactivated} deactivated."
        ))
