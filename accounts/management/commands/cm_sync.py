"""Reconcile every member's Campaign Monitor list membership with the database.

Preference saves sync immediately (accounts.signals); this nightly pass retries
anything that failed while CM was unreachable, picks up deactivated students, and
is the one-time backfill when CM is first enabled. Idempotent -- unchanged
members cost no API call unless ``--force``.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts import cm_sync
from accounts.models import Profile
from core.campaign_monitor import CampaignMonitorClient, CampaignMonitorError


class Command(BaseCommand):
    help = "Reconcile Campaign Monitor subscribers with member preferences."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Report how many members would be synced; call nothing.")
        parser.add_argument("--if-configured", action="store_true",
                            help="Exit quietly when Campaign Monitor isn't configured (for cron).")
        parser.add_argument("--force", action="store_true",
                            help="Re-push every member even if already in sync.")
        parser.add_argument("--members-only", action="store_true",
                            help="Only fill the newsletter members list (CM_MEMBERS_LIST_ID); "
                                 "digests and alerts stay as they are.")

    def _members_only(self, options):
        if not (settings.CM_API_KEY and settings.CM_CLIENT_ID and settings.CM_MEMBERS_LIST_ID):
            raise CommandError("Set CM_API_KEY, CM_CLIENT_ID and CM_MEMBERS_LIST_ID first.")
        client = CampaignMonitorClient()
        added = skipped = failed = 0
        for profile in Profile.objects.select_related("user").iterator():
            if not profile.user.is_active:
                skipped += 1
            elif options["dry_run"]:
                added += 1
            else:
                try:
                    added += cm_sync.sync_member_to_newsletter_list(profile, client)
                except CampaignMonitorError as exc:
                    failed += 1
                    self.stderr.write(f"failed {profile.user.email}: {exc}")
        verb = "would add" if options["dry_run"] else "added"
        self.stdout.write(self.style.SUCCESS(
            f"cm_sync --members-only: {verb} {added}, skipped {skipped} inactive, {failed} failed."))

    def handle(self, *args, **options):
        if options["members_only"]:
            return self._members_only(options)
        if settings.CAMPAIGN_DELIVERY != "cm":
            if options["if_configured"]:
                return
            raise CommandError("Campaign Monitor is not configured (CM_* settings).")
        synced = skipped = 0
        for profile in Profile.objects.select_related("user").iterator():
            stale = profile.cm_synced_state != cm_sync.state_hash(cm_sync.desired_state(profile))
            if not (stale or options["force"]):
                skipped += 1
                continue
            if options["dry_run"] or cm_sync.sync_profile(profile, force=options["force"]):
                synced += 1
            else:
                skipped += 1
        verb = "would sync" if options["dry_run"] else "synced"
        self.stdout.write(self.style.SUCCESS(f"cm_sync: {verb} {synced}, unchanged/failed {skipped}."))
