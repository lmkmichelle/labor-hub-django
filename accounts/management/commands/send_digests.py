"""Send email digests of newly added content to opted-in users.

Intended to be run from a scheduler, once per cohort. In production these are
the two ``crons`` entries in ``.upsun/config.yaml`` (specs are UTC)::

    # Mondays 12:00 UTC - weekly digests
    0 12 * * 1  python manage.py send_digests --frequency weekly
    # 1st of the month 12:00 UTC - monthly digests
    0 12 1 * *  python manage.py send_digests --frequency monthly
"""
from django.conf import settings
from django.core.mail import get_connection
from django.core.management.base import BaseCommand, CommandError
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

        if settings.CAMPAIGN_DELIVERY == "cm":
            return self._handle_campaign(frequency, dry_run, now)

        users = CustomUser.objects.filter(
            is_active=True,
            profile__digest_frequency=frequency,
        ).select_related("profile")

        sent = 0
        skipped = 0
        # One SMTP connection (one login) for the whole cohort, rather than
        # reconnecting -- and re-authenticating with Campaign Monitor -- per
        # recipient. open() is a no-op for the dry-run/console backends.
        connection = get_connection()
        connection.open()
        try:
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

                if send_user_digest(user, now=now, connection=connection):
                    sent += 1
                else:
                    skipped += 1
        finally:
            connection.close()

        self.stdout.write(
            self.style.SUCCESS(
                "{} digest: sent {}, skipped {}.".format(frequency, sent, skipped)
            )
        )

    def _handle_campaign(self, frequency, dry_run, now):
        """One CM campaign to the cohort's segment instead of per-user SMTP."""
        from accounts import campaigns
        from core.campaign_monitor import CampaignMonitorError
        from core.models import EmailCampaign

        if dry_run:
            last = EmailCampaign.objects.filter(
                kind=campaigns._KIND_FOR_FREQUENCY[frequency],
                status=EmailCampaign.Status.SENT).first()
            since = last.period_end if last else default_since(frequency, now)
            count = sum(len(s["items"]) for s in collect_new_content(since))
            self.stdout.write("[dry-run] would send a {} campaign with {} update(s).".format(
                frequency, count))
            return
        try:
            campaign = campaigns.send_digest_campaign(frequency, now=now)
        except (CampaignMonitorError, RuntimeError) as exc:
            raise CommandError(f"Campaign Monitor error: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(
            "{} digest: sent campaign {}.".format(frequency, campaign.cm_campaign_id) if campaign
            else "{} digest: nothing new, no campaign sent.".format(frequency)))
