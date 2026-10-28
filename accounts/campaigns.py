"""Digests and alerts as Campaign Monitor (CM) campaigns.

Under CM's terms, 1:1 transactional SMTP is for account mail; digests and alerts
are campaigns sent to list segments. See accounts.cm_sync for how members and
their interests get onto the lists.

* **Digests** -- identical for everyone in a cohort, so one campaign goes to the
  fixed "Digest weekly"/"Digest monthly" segment.
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
from accounts.digests import absolute_url, collect_new_content, default_since
from accounts.models import Profile
from core.campaign_monitor import CampaignMonitorClient
from core.models import EmailCampaign

DIGEST_LIST_TITLE = "Labor Hub Digest"
ALERT_LIST_TITLE = "Labor Hub Alerts"
MEMBERS_LIST_TITLE = "Labor Hub Members"
DIGEST_SEGMENTS = {"weekly": "Digest weekly", "monthly": "Digest monthly"}
SEGMENT_PREFIX = "Alert "
RECIPIENTS_PREFIX = "Alert recipients "
_FIELD_FOR_PREFIX = {
    "t": cm_sync.TOPICS_FIELD,
    "c": cm_sync.COUNTRIES_FIELD,
    "u": cm_sync.INSTITUTIONS_FIELD,
}
_KIND_FOR_FREQUENCY = {
    "weekly": EmailCampaign.Kind.DIGEST_WEEKLY,
    "monthly": EmailCampaign.Kind.DIGEST_MONTHLY,
}


def segment_title(token):
    """CM segment title for an interest token (``t:migration`` -> ``Alert t-migration``)."""
    return f"{SEGMENT_PREFIX}{token.replace(':', '-', 1)}"


def token_rule(token):
    """The CM segment rule matching members who follow ``token``."""
    return (f"[{_FIELD_FOR_PREFIX[token[0]]}]", f"CONTAINS |{token}|")


def _from_address():
    return parseaddr(settings.DIGEST_FROM_EMAIL)[1]


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


# -- digests -----------------------------------------------------------------

def send_digest_campaign(frequency, now=None, client=None):
    """Create and send the digest campaign for a cohort. ``None`` if nothing is new."""
    now = now or timezone.now()
    client = client or CampaignMonitorClient()
    kind = _KIND_FOR_FREQUENCY[frequency]
    last = last_sent(kind)
    since = last.period_end if last else default_since(frequency, now)
    sections = collect_new_content(since)
    if not sections:
        return None

    segments = {s["Title"]: s["SegmentID"] for s in client.segments(settings.CM_DIGEST_LIST_ID)}
    segment_id = segments.get(DIGEST_SEGMENTS[frequency])
    if segment_id is None:
        raise RuntimeError(f"CM segment '{DIGEST_SEGMENTS[frequency]}' is missing; run cm_setup.")

    total = sum(len(s["items"]) for s in sections)
    subject = "Labor Hub digest: {} new update{}".format(total, "" if total == 1 else "s")
    html, text = _render("digest", sections, "Labor Hub digest")
    campaign = EmailCampaign.objects.create(
        kind=kind, subject=subject, html=html, text=text, period_start=since, period_end=now)
    return _create_and_send(client, campaign, [segment_id])


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
    for segment in client.segments(settings.CM_ALERT_LIST_ID):
        if segment["Title"].startswith(SEGMENT_PREFIX):
            client.delete_segment(segment["SegmentID"])
    interest_ids = {
        token: client.create_segment(
            settings.CM_ALERT_LIST_ID, segment_title(token), [[token_rule(token)]])
        for token in sorted(relevant)
    }
    recipients_id = client.create_segment(
        settings.CM_ALERT_LIST_ID, f"{RECIPIENTS_PREFIX}{now:%Y-%m-%d}",
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
