"""Create (or find) everything this site needs in Campaign Monitor, by name.

Idempotent: run it on every deploy. It makes the Newsletter and Alerts lists with their
custom fields, the "Newsletter weekly/monthly" segments, and the unsubscribe webhooks,
then records the list ids (core.cm_lists) so no one copies ids into environment
variables. Only ``CM_API_KEY`` and ``CM_CLIENT_ID`` are configured by hand.

One-time carry-over: the first newsletter went to an interim "Labor Hub Members" list.
Anyone who unsubscribed from it is switched off here, *before* the newsletter list id
is recorded. Until the id is recorded nothing is pushed to the newsletter list
(accounts.cm_sync), so a failure here can never re-add someone who opted out.
"""
from django.conf import settings
from django.urls import reverse

from accounts import campaigns, cm_sync
from accounts.models import Profile
from core import cm_lists
from core.links import absolute_url

INTERIM_LIST_TITLE = "Labor Hub Members"
OPTOUTS_IMPORTED = "launch_optouts_imported"


def _ensure_list(client, key, fields, say):
    title = cm_lists.TITLES[key]
    list_id = cm_lists.list_id(key)
    if not list_id:
        found = {entry["Name"]: entry["ListID"] for entry in client.lists()}
        list_id = found.get(title)
        if list_id is None:
            list_id = client.create_list(title)
            say(f"created list '{title}'")
    have = {f["FieldName"] for f in client.custom_fields(list_id)}
    for name in fields:
        if name not in have:
            client.create_custom_field(list_id, name)
            say(f"created field {title}.{name}")
    return list_id


def _ensure_segments(client, newsletter_id, say):
    existing = {s["Title"] for s in client.segments(newsletter_id)}
    for frequency, title in campaigns.NEWSLETTER_SEGMENTS.items():
        if title not in existing:
            client.create_segment(
                newsletter_id, title, [[(f"[{cm_sync.NEWSLETTER_FIELD}]", f"EQUALS {frequency}")]])
            say(f"created segment '{title}'")


def _ensure_webhooks(client, list_ids, say):
    if not settings.SITE_URL.startswith("https://") or not settings.CM_WEBHOOK_SECRET:
        say("skipped webhooks: SITE_URL is not a public https address here")
        return
    url = absolute_url(reverse("cm_webhook", kwargs={"secret": settings.CM_WEBHOOK_SECRET}))
    for list_id in list_ids:
        if not any(h["Url"] == url for h in client.webhooks(list_id)):
            client.create_webhook(list_id, url, events=("Deactivate",))
            say(f"registered webhook on {list_id[:6]}")


def import_launch_optouts(client, say):
    """Switch off the newsletter for everyone who unsubscribed from the interim list.

    Returns how many members were switched. A no-op when the list never existed or
    this has already run."""
    if cm_lists.stored(OPTOUTS_IMPORTED):
        return 0
    interim = {e["Name"]: e["ListID"] for e in client.lists()}.get(INTERIM_LIST_TITLE)
    switched = 0
    if interim:
        for email in client.all_unsubscribed(interim):
            # update(): CM already knows, so don't echo it back through the signal.
            switched += Profile.objects.filter(user__email__iexact=email).exclude(
                newsletter_frequency=Profile.NewsletterFrequency.OFF,
            ).update(newsletter_frequency=Profile.NewsletterFrequency.OFF)
        say(f"imported {switched} opt-out(s) from '{INTERIM_LIST_TITLE}'")
    cm_lists.remember(OPTOUTS_IMPORTED, "done")
    return switched


def ensure_resources(client, say=lambda message: None):
    """Provision everything and record the list ids. Raises on any CM error."""
    alerts_id = _ensure_list(client, cm_lists.ALERTS, cm_sync.ALERT_FIELDS, say)
    cm_lists.remember(cm_lists.ALERTS, alerts_id)
    newsletter_id = _ensure_list(client, cm_lists.NEWSLETTER, (cm_sync.NEWSLETTER_FIELD,), say)
    _ensure_segments(client, newsletter_id, say)
    _ensure_webhooks(client, (newsletter_id, alerts_id), say)
    import_launch_optouts(client, say)
    # Only now may the sync start pushing members to the newsletter list.
    cm_lists.remember(cm_lists.NEWSLETTER, newsletter_id)
    return {cm_lists.NEWSLETTER: newsletter_id, cm_lists.ALERTS: alerts_id}
