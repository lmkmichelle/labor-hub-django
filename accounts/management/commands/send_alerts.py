"""Send weekly topic/country alert emails to subscribed members.

Intended to be run from a scheduler, once a week. In production this is the
``alerts-weekly`` cron entry in ``.upsun/config.yaml`` (spec is UTC)::

    # Fridays 12:00 UTC - weekly alerts
    0 12 * * 5  python manage.py send_alerts
"""
from django.core.mail import get_connection
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.alerts import collect_alert_matches, default_since, send_user_alerts
from accounts.models import CustomUser


class Command(BaseCommand):
    help = "Send weekly topic/country alert emails to subscribed members."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report who would receive an alert without sending anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()

        # Filtered in Python, not with a JSON-equality query, for the same
        # reason accounts.alerts.collect_alert_matches matches in Python:
        # JSON comparison isn't guaranteed to behave the same on SQLite and
        # the MariaDB used in production. The active-user table is small
        # enough that this costs nothing.
        users = [
            user for user in (
                CustomUser.objects.filter(is_active=True).select_related("profile")
            )
            if user.profile.alert_topics or user.profile.alert_countries
        ]

        sent = 0
        skipped = 0
        connection = get_connection()
        connection.open()
        try:
            for user in users:
                if dry_run:
                    since = user.profile.last_alert_sent_at or default_since(now)
                    count = sum(
                        len(section["items"])
                        for section in collect_alert_matches(user.profile, since)
                    )
                    if count:
                        self.stdout.write(
                            "[dry-run] would send {} match(es) to {}".format(
                                count, user.email
                            )
                        )
                        sent += 1
                    else:
                        skipped += 1
                    continue

                if send_user_alerts(user, now=now, connection=connection):
                    sent += 1
                else:
                    skipped += 1
        finally:
            connection.close()

        self.stdout.write(
            self.style.SUCCESS(
                "alerts: sent {}, skipped {}.".format(sent, skipped)
            )
        )
