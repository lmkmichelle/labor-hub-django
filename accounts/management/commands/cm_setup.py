"""One-time (idempotent) Campaign Monitor setup for the digest and alerts lists.

Creates the two lists, their custom fields and the fixed digest segments in the CM
account the API key belongs to, then prints the list ids to store as the
``CM_DIGEST_LIST_ID`` / ``CM_ALERT_LIST_ID`` variables. Safe to re-run: anything
that already exists (matched by title) is left alone. With ``--webhooks`` it also
registers the unsubscribe/bounce webhooks pointing at this site.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from accounts import campaigns, cm_sync
from accounts.digests import absolute_url
from core.campaign_monitor import CampaignMonitorClient, CampaignMonitorError

ALERT_FIELDS = cm_sync.ALERT_FIELDS
DIGEST_FIELDS = (cm_sync.DIGEST_FIELD,)


class Command(BaseCommand):
    help = "Create the Campaign Monitor lists, custom fields and digest segments."

    def add_arguments(self, parser):
        parser.add_argument("--webhooks", action="store_true",
                            help="Also register the Deactivate webhooks (needs CM_WEBHOOK_SECRET and a public SITE_URL).")

    def handle(self, *args, **options):
        if not (settings.CM_API_KEY and settings.CM_CLIENT_ID):
            raise CommandError("Set CM_API_KEY and CM_CLIENT_ID first.")
        client = CampaignMonitorClient()
        try:
            digest_id = self._ensure_list(client, campaigns.DIGEST_LIST_TITLE, DIGEST_FIELDS)
            alert_id = self._ensure_list(client, campaigns.ALERT_LIST_TITLE, ALERT_FIELDS)
            members_id = self._ensure_list(client, campaigns.MEMBERS_LIST_TITLE, [])
            existing = {s["Title"] for s in client.segments(digest_id)}
            for frequency, title in campaigns.DIGEST_SEGMENTS.items():
                if title not in existing:
                    client.create_segment(
                        digest_id, title, [[(f"[{cm_sync.DIGEST_FIELD}]", f"EQUALS {frequency}")]])
                    self.stdout.write(f"created segment '{title}'")
            if options["webhooks"]:
                self._ensure_webhooks(client, digest_id, alert_id)
        except CampaignMonitorError as exc:
            raise CommandError(f"Campaign Monitor error: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(
            f"Set these (Upsun sensitive/project variables):\n"
            f"  CM_DIGEST_LIST_ID={digest_id}\n  CM_ALERT_LIST_ID={alert_id}\n  CM_MEMBERS_LIST_ID={members_id}"))

    def _ensure_list(self, client, title, fields):
        found = {entry["Name"]: entry["ListID"] for entry in client.lists()}
        list_id = found.get(title)
        if list_id is None:
            list_id = client.create_list(title)
            self.stdout.write(f"created list '{title}'")
        have = {f["FieldName"] for f in client.custom_fields(list_id)}
        for name in fields:
            if name not in have:
                client.create_custom_field(list_id, name)
                self.stdout.write(f"created field {title}.{name}")
        return list_id

    def _ensure_webhooks(self, client, digest_id, alert_id):
        if not settings.CM_WEBHOOK_SECRET:
            raise CommandError("Set CM_WEBHOOK_SECRET before registering webhooks.")
        url = absolute_url(reverse("cm_webhook", kwargs={"secret": settings.CM_WEBHOOK_SECRET}))
        for list_id in (digest_id, alert_id):
            if not any(h["Url"] == url for h in client.webhooks(list_id)):
                client.create_webhook(list_id, url, events=("Deactivate",))
                self.stdout.write(f"registered webhook on {list_id[:6]}")
