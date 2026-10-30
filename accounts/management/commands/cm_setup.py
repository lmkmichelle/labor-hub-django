"""Create (or find) the Campaign Monitor lists, fields, segments and webhooks.

    python manage.py cm_setup                 # report what it did
    python manage.py cm_setup --if-configured # no-op without CM_API_KEY/CM_CLIENT_ID

Runs on every deploy and before the nightly sync (see .upsun/config.yaml), so nothing
needs doing by hand beyond setting ``CM_API_KEY`` and ``CM_CLIENT_ID``. Safe to re-run:
anything that already exists (matched by name) is left alone. The work lives in
accounts.cm_provision.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.cm_provision import ensure_resources
from core.campaign_monitor import CampaignMonitorClient, CampaignMonitorError


class Command(BaseCommand):
    help = "Create the Campaign Monitor lists, fields, segments and webhooks."

    def add_arguments(self, parser):
        parser.add_argument("--if-configured", action="store_true",
                            help="Exit quietly when Campaign Monitor isn't configured (for deploys/cron).")

    def handle(self, *args, **options):
        if not (settings.CM_API_KEY and settings.CM_CLIENT_ID):
            if options["if_configured"]:
                return
            raise CommandError("Set CM_API_KEY and CM_CLIENT_ID first.")
        try:
            ids = ensure_resources(CampaignMonitorClient(), say=self.stdout.write)
        except CampaignMonitorError as exc:
            raise CommandError(f"Campaign Monitor error: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(
            "Campaign Monitor is set up: "
            + ", ".join(f"{key} list {value}" for key, value in ids.items())))
