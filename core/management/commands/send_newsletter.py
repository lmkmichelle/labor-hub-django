"""Send the Labor Hub newsletter through Campaign Monitor.

    python manage.py send_newsletter --scheduled                 # what the Monday cron runs
    python manage.py send_newsletter --test-to you@cornell.edu   # preview to you only
    python manage.py send_newsletter --test-to a@x.edu,b@x.edu   # up to 5 addresses
    python manage.py send_newsletter --send                      # one-off, to every subscriber

``--scheduled`` sends to the weekly cohort, plus the monthly cohort in the first seven
days of the month (one campaign, one issue number) and sends nothing in a week with
nothing to list. ``--send`` ignores the cohorts and goes to the whole Newsletter list.
Sent from CAMPAIGN_FROM_EMAIL (not the shared laborhub@ inbox); replies go to
REPLY_TO_EMAIL when set. Who is on the list follows each member's Newsletter
setting automatically (accounts.cm_sync). Edit the per-issue text in
core/newsletter.py first. To look at the HTML without sending anything:

    python manage.py send_test_emails --preview --only newsletter
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.campaigns import (
    _create_and_send, _from_address, newsletter_cohorts, send_newsletter_campaign,
)
from core import cm_lists
from core.campaign_monitor import CampaignMonitorClient, CampaignMonitorError
from core.newsletter import create_newsletter_campaign


class Command(BaseCommand):
    help = "Send the newsletter as a Campaign Monitor campaign (or a preview to a few addresses)."

    def add_arguments(self, parser):
        parser.add_argument("--test-to", metavar="EMAIL[,EMAIL...]",
                            help="Send a preview to these addresses only (comma-separated, "
                                 "at most 5).")
        parser.add_argument("--send", action="store_true",
                            help="One-off: send to everyone on the Newsletter list.")
        parser.add_argument("--scheduled", action="store_true",
                            help="Send to the cohorts due today (for the weekly cron).")

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
        try:
            if scheduled:
                self._scheduled(client)
            elif send:
                campaign = create_newsletter_campaign()
                _create_and_send(client, campaign, [],
                                 list_ids=[cm_lists.list_id(cm_lists.NEWSLETTER)])
                self.stdout.write(self.style.SUCCESS(f"Sent: {campaign.subject}"))
            else:
                self._preview(client, create_newsletter_campaign(), test_to)
        except CampaignMonitorError as exc:
            raise CommandError(f"Campaign Monitor error: {exc}") from exc

    def _scheduled(self, client):
        now = timezone.now()
        cohorts = newsletter_cohorts(now)
        campaign = send_newsletter_campaign(cohorts, now=now, client=client)
        self.stdout.write(self.style.SUCCESS(
            f"newsletter: sent '{campaign.subject}' to {', '.join(cohorts)}." if campaign
            else "newsletter: nothing to list this week, no campaign sent."))

    def _preview(self, client, campaign, addresses):
        from django.urls import reverse
        from core.links import absolute_url
        html_url, text_url = (
            absolute_url(reverse("campaign_snapshot", kwargs={"token": campaign.token, "ext": ext}))
            for ext in ("html", "txt"))
        campaign.cm_campaign_id = client.create_campaign(
            name=f"Newsletter preview {timezone.now():%Y-%m-%d %H:%M}", subject=campaign.subject,
            html_url=html_url, text_url=text_url,
            list_ids=[cm_lists.list_id(cm_lists.NEWSLETTER)],
            segment_ids=[], from_name="The Labor Hub", from_email=_from_address(),
            reply_to=settings.REPLY_TO_EMAIL or _from_address())
        client.send_preview(campaign.cm_campaign_id, addresses)
        # A preview is never a sent issue: leave it prepared so the issue number holds.
        campaign.save()
        self.stdout.write(self.style.SUCCESS(
            f"Preview of '{campaign.subject}' sent to {', '.join(addresses)}"))
