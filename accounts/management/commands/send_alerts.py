"""Send weekly topic/country alert emails to subscribed members.

Intended to be run from a scheduler, once a week. In production this is the
``alerts-weekly`` cron entry in ``.upsun/config.yaml`` (spec is UTC)::

    # Fridays 12:00 UTC - weekly alerts
    0 12 * * 5  python manage.py send_alerts
"""
from django.conf import settings
from django.core.mail import get_connection
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.alerts import collect_alert_matches, default_since, send_user_alerts
from accounts.models import CustomUser


class Command(BaseCommand):
    help = "Send weekly topic/country alert emails to subscribed members."

    def add_arguments(self, parser):
        parser.add_argument(
            "--prepare", action="store_true",
            help="Campaign Monitor mode: build the week's campaign and interest "
                 "segments (run an hour before --send).")
        parser.add_argument(
            "--send", action="store_true",
            help="Campaign Monitor mode: send the prepared campaign.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report who would receive an alert without sending anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()

        if settings.CAMPAIGN_DELIVERY == "cm":
            return self._handle_campaign(options, now)
        if options["prepare"]:
            # The 11:00 cron runs this on every environment; only CM needs a prepare step.
            self.stdout.write("alerts: --prepare is a no-op without Campaign Monitor.")
            return
        if options["send"]:
            raise CommandError("--send needs the Campaign Monitor settings (CM_*).")

        # Filtered in Python, not with a JSON-equality query, for the same
        # reason accounts.alerts.collect_alert_matches matches in Python:
        # JSON comparison isn't guaranteed to behave the same on SQLite and
        # the MariaDB used in production. The active-user table is small
        # enough that this costs nothing.
        users = [
            user for user in (
                CustomUser.objects.filter(is_active=True).select_related("profile")
            )
            if (user.profile.alert_topics or user.profile.alert_countries
                or user.profile.alert_universities)
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

    def _handle_campaign(self, options, now):
        """Alerts as one CM campaign: ``--prepare`` then, an hour later, ``--send``."""
        from accounts import campaigns
        from core.campaign_monitor import CampaignMonitorError

        if options["prepare"] and options["send"]:
            raise CommandError("Use --prepare or --send, not both (plain run == --send).")
        try:
            if options["prepare"]:
                campaign = campaigns.prepare_alerts(now=now)
                self.stdout.write(
                    "alerts: prepared '{}'.".format(campaign.subject) if campaign
                    else "alerts: nothing new matches anyone, no campaign prepared.")
            else:
                campaign = campaigns.send_prepared_alerts()
                self.stdout.write(self.style.SUCCESS(
                    "alerts: sent campaign {}.".format(campaign.cm_campaign_id) if campaign
                    else "alerts: no prepared campaign to send."))
        except CampaignMonitorError as exc:
            raise CommandError(f"Campaign Monitor error: {exc}") from exc
