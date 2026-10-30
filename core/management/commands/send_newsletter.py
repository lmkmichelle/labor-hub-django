"""Send the Labor Hub newsletter through Campaign Monitor.

    python manage.py send_newsletter --test-to you@cornell.edu   # preview to you only
    python manage.py send_newsletter --test-to a@x.edu,b@x.edu   # up to 5 addresses
    python manage.py send_newsletter --send                      # to every member

Sent from DIGEST_FROM_EMAIL (not the shared laborhub@ inbox); replies go to
REPLY_TO_EMAIL when set. Recipients are the "Labor Hub Members" CM list
(CM_MEMBERS_LIST_ID), kept in step by cm_sync. Edit the per-issue text in
core/newsletter.py first. To look at the HTML without sending anything:

    python manage.py send_test_emails --preview --only newsletter
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.campaigns import _create_and_send, _from_address
from core.campaign_monitor import CampaignMonitorClient, CampaignMonitorError
from core.newsletter import create_newsletter_campaign


class Command(BaseCommand):
    help = "Send the newsletter as a Campaign Monitor campaign (or a preview to one address)."

    def add_arguments(self, parser):
        parser.add_argument("--test-to", metavar="EMAIL[,EMAIL...]",
                            help="Send a preview to these addresses only (comma-separated, "
                                 "at most 5).")
        parser.add_argument("--send", action="store_true",
                            help="Send to the whole members list.")

    def handle(self, *args, **options):
        test_to, send = options["test_to"], options["send"]
        if test_to:
            test_to = [a.strip() for a in test_to.split(",") if a.strip()]
            if not 1 <= len(test_to) <= 5:
                raise CommandError("--test-to takes 1 to 5 addresses (Campaign Monitor's limit).")
        if bool(test_to) == bool(send):
            raise CommandError("Give exactly one of --test-to EMAIL or --send.")
        if not (settings.CM_API_KEY and settings.CM_CLIENT_ID and settings.CM_MEMBERS_LIST_ID):
            raise CommandError(
                "Set CM_API_KEY, CM_CLIENT_ID and CM_MEMBERS_LIST_ID (run cm_setup) first.")
        client = CampaignMonitorClient()
        campaign = create_newsletter_campaign()
        try:
            if send:
                _create_and_send(client, campaign, [], list_ids=[settings.CM_MEMBERS_LIST_ID])
                self.stdout.write(self.style.SUCCESS(f"Sent: {campaign.subject}"))
            else:
                self._preview(client, campaign, test_to)
        except CampaignMonitorError as exc:
            raise CommandError(f"Campaign Monitor error: {exc}") from exc

    def _preview(self, client, campaign, addresses):
        from django.urls import reverse
        from accounts.digests import absolute_url
        html_url, text_url = (
            absolute_url(reverse("campaign_snapshot", kwargs={"token": campaign.token, "ext": ext}))
            for ext in ("html", "txt"))
        campaign.cm_campaign_id = client.create_campaign(
            name=f"Newsletter preview {timezone.now():%Y-%m-%d %H:%M}", subject=campaign.subject,
            html_url=html_url, text_url=text_url, list_ids=[settings.CM_MEMBERS_LIST_ID],
            segment_ids=[], from_name="The Labor Hub", from_email=_from_address(),
            reply_to=settings.REPLY_TO_EMAIL or _from_address())
        client.send_preview(campaign.cm_campaign_id, addresses)
        # A preview is never a sent issue: leave it prepared so the issue number holds.
        campaign.save()
        self.stdout.write(self.style.SUCCESS(f"Preview of '{campaign.subject}' sent to {", ".join(addresses)}"))
