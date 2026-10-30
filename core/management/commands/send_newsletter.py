"""Send the Labor Hub newsletter through Campaign Monitor.

    python manage.py send_newsletter --scheduled                 # what the Friday cron runs
    python manage.py send_newsletter --test-to you@cornell.edu   # preview to you only
    python manage.py send_newsletter --test-to a@x.edu,b@x.edu   # up to 5 addresses
    python manage.py send_newsletter --send --kind monthly       # one-off, to that cohort

There are two newsletters: weekly (every Friday) and monthly (the first Friday of the
month), each its own issue sent to its own segment of the Newsletter list. ``--scheduled``
sends whichever is due, skipping one that is paused in the admin, was sent recently, or has
nothing to list. Admins can also preview, pause and send from the admin's Newsletters page.
Sent from CAMPAIGN_FROM_EMAIL (not the shared laborhub@ inbox); replies go to
REPLY_TO_EMAIL when set. Who is on each segment follows each member's Newsletter setting
automatically (accounts.cm_sync). Edit the per-issue text in core/newsletter.py first. To
look at the HTML without sending anything:

    python manage.py send_test_emails --preview --only newsletter
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.campaigns import newsletter_due, preview_newsletter_issue, send_newsletter_issue
from core import cm_lists
from core.campaign_monitor import CampaignMonitorClient, CampaignMonitorError
from core.newsletter import KINDS, WEEKLY


class Command(BaseCommand):
    help = "Send the newsletter as a Campaign Monitor campaign (or a preview to a few addresses)."

    def add_arguments(self, parser):
        parser.add_argument("--test-to", metavar="EMAIL[,EMAIL...]",
                            help="Send a preview to these addresses only (comma-separated, "
                                 "at most 5).")
        parser.add_argument("--send", action="store_true",
                            help="One-off: send now to everyone in --kind's segment.")
        parser.add_argument("--scheduled", action="store_true",
                            help="Send whichever newsletters are due today (for the Friday cron).")
        parser.add_argument("--kind", choices=list(KINDS), default=WEEKLY,
                            help="Which newsletter for --send / --test-to (default weekly).")

    def handle(self, *args, **options):
        test_to, send, scheduled = options["test_to"], options["send"], options["scheduled"]
        if test_to:
            test_to = [a.strip() for a in test_to.split(",") if a.strip()]
            if not 1 <= len(test_to) <= 5:
                raise CommandError("--test-to takes 1 to 5 addresses (Campaign Monitor's limit).")
        if [bool(test_to), send, scheduled].count(True) != 1:
            raise CommandError("Give exactly one of --scheduled, --send or --test-to EMAIL.")
        ready = bool(settings.CM_API_KEY and settings.CM_CLIENT_ID
                     and cm_lists.list_id(cm_lists.NEWSLETTER))
        if not ready:
            if scheduled:
                self.stdout.write("newsletter: Campaign Monitor is not set up, nothing sent.")
                return
            raise CommandError(
                "Set CM_API_KEY and CM_CLIENT_ID, then run cm_setup, first.")
        client = CampaignMonitorClient()
        kind = options["kind"]
        try:
            if scheduled:
                self._scheduled(client)
            elif send:
                campaign = send_newsletter_issue(kind, client=client)
                self.stdout.write(self.style.SUCCESS(f"Sent: {campaign.subject}"))
            else:
                campaign = preview_newsletter_issue(kind, test_to, client=client)
                self.stdout.write(self.style.SUCCESS(
                    f"Preview of '{campaign.subject}' sent to {', '.join(test_to)}"))
        except CampaignMonitorError as exc:
            raise CommandError(f"Campaign Monitor error: {exc}") from exc

    def _scheduled(self, client):
        now = timezone.now()
        for kind in KINDS:
            due, reason = newsletter_due(kind, now)
            if not due:
                self.stdout.write(f"newsletter ({kind}): skipped, {reason}.")
                continue
            campaign = send_newsletter_issue(kind, now=now, client=client, only_if_content=True)
            self.stdout.write(self.style.SUCCESS(
                f"newsletter ({kind}): sent '{campaign.subject}'." if campaign
                else f"newsletter ({kind}): nothing to list, no campaign sent."))
