"""The newsletter and alerts as Campaign Monitor (CM) campaigns.

Under CM's terms, 1:1 transactional SMTP is for account mail; the newsletter and
alerts are campaigns sent to list segments. See accounts.cm_sync for how members and
their interests get onto the lists.

* **Newsletter** -- identical for everyone in a cohort: the weekly issue goes to the
  "Newsletter weekly" segment every Friday, the monthly issue to "Newsletter monthly" on
  the first Friday of the month. Admins can pause either or send it by hand.
* **Alerts** -- each member must see only what *they* follow. One campaign is
  sent to everyone with at least one match, and every item is wrapped in CM
  ``[ifmemberof:...]`` tags naming the interest segments it is relevant to, so
  CM shows each recipient only their matching items. Interest segments are
  built from the delimited-token custom fields (``AlertTopics CONTAINS
  "|t:migration|"``). CM needs time to calculate new segments, so alerts are
  *prepared* an hour before they are *sent*.
"""
from email.utils import parseaddr

from django.conf import settings
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from accounts import cm_sync
from accounts.alerts import ALERT_WINDOW, profile_tokens, week_items
from accounts.models import Profile
from core import cm_lists
from core.campaign_monitor import CampaignMonitorClient
from core.links import absolute_url
from core.models import EmailCampaign, NewsletterSchedule
from core.newsletter import (
    KINDS, MONTHLY, WEEKLY, create_newsletter_campaign, last_sent_issue,
)

NEWSLETTER_LIST_TITLE = cm_lists.TITLES[cm_lists.NEWSLETTER]
ALERT_LIST_TITLE = cm_lists.TITLES[cm_lists.ALERTS]
NEWSLETTER_SEGMENTS = {kind: spec["segment"] for kind, spec in KINDS.items()}
SEGMENT_PREFIX = "Alert "
RECIPIENTS_PREFIX = "Alert recipients "
_FIELD_FOR_PREFIX = {
    "t": cm_sync.TOPICS_FIELD,
    "c": cm_sync.COUNTRIES_FIELD,
    "u": cm_sync.INSTITUTIONS_FIELD,
}


def segment_title(token):
    """CM segment title for an interest token (``t:migration`` -> ``Alert t-migration``)."""
    return f"{SEGMENT_PREFIX}{token.replace(':', '-', 1)}"


def token_rule(token):
    """The CM segment rule matching members who follow ``token``."""
    return (f"[{_FIELD_FOR_PREFIX[token[0]]}]", f"CONTAINS |{token}|")


def _from_address():
    return parseaddr(settings.CAMPAIGN_FROM_EMAIL)[1]


def _render(kind, sections, title):
    context = {
        "title": title,
        "sections": sections,
        "site_url": settings.SITE_URL.rstrip("/"),
        "manage_url": absolute_url(reverse("settings")),
        # Campaign HTML is fetched and delivered by CM, so no cid: attachment.
        "logo_src": absolute_url(static("images/logo_small.png")),
    }
    return (render_to_string(f"emails/campaign_{kind}.html", context),
            render_to_string(f"emails/campaign_{kind}.txt", context))


def last_sent(kind):
    return EmailCampaign.objects.filter(kind=kind, status=EmailCampaign.Status.SENT).first()


def _create_and_send(client, campaign, segment_ids, list_ids=()):
    html_url, text_url = (
        absolute_url(reverse("campaign_snapshot", kwargs={"token": campaign.token, "ext": ext}))
        for ext in ("html", "txt"))
    try:
        campaign.cm_campaign_id = client.create_campaign(
            name=f"{campaign.get_kind_display()} {campaign.created_at:%Y-%m-%d}",
            subject=campaign.subject, html_url=html_url, text_url=text_url,
            list_ids=list(list_ids), segment_ids=segment_ids,
            from_name="The Labor Hub", from_email=_from_address(),
            reply_to=settings.REPLY_TO_EMAIL or _from_address(),
        )
        client.send_campaign(campaign.cm_campaign_id, settings.CONTACT_EMAIL)
    except Exception as exc:
        campaign.status = EmailCampaign.Status.FAILED
        campaign.error = str(exc)[:1000]
        campaign.save()
        raise
    campaign.status = EmailCampaign.Status.SENT
    campaign.sent_at = timezone.now()
    campaign.save()
    return campaign


# -- newsletter --------------------------------------------------------------

def newsletter_due(kind, now=None):
    """Whether the scheduled run should send ``kind`` now: ``(due, reason)``.

    Not due while paused in the admin, within the guard window after a send (so a
    manual send is not followed by a duplicate), or, for the monthly issue, after the
    first seven days of the month (the first Friday)."""
    now = now or timezone.now()
    if NewsletterSchedule.for_kind(kind).paused:
        return False, "paused in the admin"
    last = last_sent_issue(kind)
    if last and last.sent_at and now - last.sent_at < KINDS[kind]["guard"]:
        return False, f"already sent {(now - last.sent_at).days} day(s) ago"
    if kind == MONTHLY and timezone.localdate(now).day > 7:
        return False, "not the first Friday of the month"
    return True, ""


def send_newsletter_issue(kind=WEEKLY, now=None, client=None, only_if_content=False):
    """Create the ``kind`` issue and send it to its segment of the Newsletter list.

    ``None`` when ``only_if_content`` and there is nothing to list."""
    now = now or timezone.now()
    client = client or CampaignMonitorClient()
    campaign = create_newsletter_campaign(kind, now, only_if_content=only_if_content)
    if campaign is None:
        return None
    segments = {s["Title"]: s["SegmentID"]
                for s in client.segments(cm_lists.list_id(cm_lists.NEWSLETTER))}
    try:
        segment_ids = [segments[NEWSLETTER_SEGMENTS[kind]]]
    except KeyError as missing:
        raise RuntimeError(f"CM segment {missing} is missing; run cm_setup.") from missing
    return _create_and_send(client, campaign, segment_ids)


def preview_newsletter_issue(kind, addresses, client=None):
    """Send a preview of the current ``kind`` issue to up to 5 addresses. The issue is
    stored but never marked sent, so the issue number holds."""
    client = client or CampaignMonitorClient()
    campaign = create_newsletter_campaign(kind)
    html_url, text_url = (
        absolute_url(reverse("campaign_snapshot", kwargs={"token": campaign.token, "ext": ext}))
        for ext in ("html", "txt"))
    campaign.cm_campaign_id = client.create_campaign(
        name=f"Newsletter preview {timezone.now():%Y-%m-%d %H:%M}", subject=campaign.subject,
        html_url=html_url, text_url=text_url,
        list_ids=[cm_lists.list_id(cm_lists.NEWSLETTER)], segment_ids=[],
        from_name="The Labor Hub", from_email=_from_address(),
        reply_to=settings.REPLY_TO_EMAIL or _from_address())
    client.send_preview(campaign.cm_campaign_id, addresses)
    campaign.save()
    return campaign


# -- alerts ------------------------------------------------------------------

def followed_tokens():
    """Union of interest tokens followed by any active alert subscriber."""
    followed = set()
    for profile in Profile.objects.filter(user__is_active=True).select_related("user"):
        followed |= profile_tokens(profile)
    return followed


def prepare_alerts(now=None, client=None):
    """Build the next send's campaign snapshot and interest segments (no send yet).

    Returns the prepared ``EmailCampaign``, or ``None`` when nothing new matches
    anyone's alerts.
    """
    now = now or timezone.now()
    client = client or CampaignMonitorClient()
    last = last_sent(EmailCampaign.Kind.ALERTS)
    since = last.period_end if last else now - ALERT_WINDOW

    publications, visits = week_items(since)
    followed = followed_tokens()
    kept = {
        "publications": [(i, t & followed) for i, t in publications if t & followed],
        "visits": [(i, t & followed) for i, t in visits if t & followed],
    }
    relevant = set()
    for rows in kept.values():
        for _, tokens in rows:
            relevant |= tokens
    if not relevant:
        return None

    # Segments: drop last run's, then create one per relevant token plus the
    # union ("recipients") segment the campaign is actually sent to.
    for segment in client.segments(cm_lists.list_id(cm_lists.ALERTS)):
        if segment["Title"].startswith(SEGMENT_PREFIX):
            client.delete_segment(segment["SegmentID"])
    interest_ids = {
        token: client.create_segment(
            cm_lists.list_id(cm_lists.ALERTS), segment_title(token), [[token_rule(token)]])
        for token in sorted(relevant)
    }
    recipients_id = client.create_segment(
        cm_lists.list_id(cm_lists.ALERTS), f"{RECIPIENTS_PREFIX}{now:%Y-%m-%d}",
        [[token_rule(token) for token in sorted(relevant)]])

    labels = {"publications": "New papers matching your topics",
              "visits": "New visits matching your alerts"}
    sections = []
    for key, rows in kept.items():
        if not rows:
            continue
        items = []
        for item, tokens in rows:
            refs = ",".join(
                f'"{ALERT_LIST_TITLE}|{segment_title(t)}"' for t in sorted(tokens))
            items.append({
                **item,
                "cm_open": mark_safe(f"[ifmemberof:{refs}]"),
                "cm_close": mark_safe("[endif]"),
                "cm_open_text": f"[ifmemberof:{refs}]\n",
                "cm_close_text": "[endif]\n",
            })
        sections.append({"key": key, "label": labels[key], "items": items})

    html, text = _render("alerts", sections, "Labor Hub alerts")
    EmailCampaign.objects.filter(
        kind=EmailCampaign.Kind.ALERTS, status=EmailCampaign.Status.PREPARED,
    ).update(status=EmailCampaign.Status.FAILED, error="superseded by a newer preparation")
    return EmailCampaign.objects.create(
        kind=EmailCampaign.Kind.ALERTS,
        subject=f"Your Labor Hub alerts: week of {now:%b} {now.day}",
        html=html, text=text, period_start=since, period_end=now,
        segment_ids={"recipients": recipients_id, "interests": interest_ids},
    )


def send_prepared_alerts(client=None):
    """Send the latest prepared alerts campaign (a sent one is never resent)."""
    client = client or CampaignMonitorClient()
    campaign = EmailCampaign.objects.filter(
        kind=EmailCampaign.Kind.ALERTS, status=EmailCampaign.Status.PREPARED).first()
    if campaign is None:
        return None
    return _create_and_send(client, campaign, [campaign.segment_ids["recipients"]])
