"""Send email digests of newly added content to opted-in users.

Intended to be run from the host's scheduler (cron on Media3), once per
cohort, e.g.::

    # Mondays 07:00 - weekly digests
    0 7 * * 1  python manage.py send_digests --frequency weekly
    # 1st of the month 07:00 - monthly digests
    0 7 1 * *  python manage.py send_digests --frequency monthly
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.digests import collect_new_content, default_since, send_user_digest
from accounts.models import CustomUser


class Command(BaseCommand):
    help = "Send email digests of newly added content to opted-in users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--frequency",
            choices=["weekly", "monthly"],
            required=True,
            help="Which digest cohort to send (matches Profile.digest_frequency).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report who would receive a digest without sending anything.",
        )

    def handle(self, *args, **options):
        frequency = options["frequency"]
        dry_run = options["dry_run"]
        now = timezone.now()

        users = CustomUser.objects.filter(
            is_active=True,
            profile__digest_frequency=frequency,
        ).select_related("profile")

        sent = 0
        skipped = 0
        for user in users:
            if dry_run:
                since = user.profile.last_digest_sent_at or default_since(
                    frequency, now
                )
                count = sum(
                    len(section["items"])
                    for section in collect_new_content(since)
                )
                if count:
                    self.stdout.write(
                        "[dry-run] would send {} update(s) to {}".format(
                            count, user.email
                        )
                    )
                    sent += 1
                else:
                    skipped += 1
                continue

            if send_user_digest(user, now=now):
                sent += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                "{} digest: sent {}, skipped {}.".format(frequency, sent, skipped)
            )
        )
