"""Keep Campaign Monitor (CM) subscriber lists in step with member preferences.

The newsletter and alerts are CM *campaigns*, sent to list segments. A member is on
the newsletter list when ``newsletter_frequency`` is weekly/monthly, and on the
alerts list when any alert topic/country/institution is set. Alert interests are stored in
the list's custom fields as ``|``-delimited tokens (``|t:migration|c:US|``) so a
CM segment rule ``AlertTopics CONTAINS "|t:migration|"`` means "follows migration".

``sync_profile`` is idempotent and diff-based: it hashes the desired CM state and
returns without a network call when it equals ``Profile.cm_synced_state``.
"""
import hashlib
import json
import logging

from django.conf import settings
from django.db import transaction
from django.utils.text import slugify

from core import cm_lists
from core.campaign_monitor import CampaignMonitorClient, CampaignMonitorError, is_configured

logger = logging.getLogger(__name__)

NEWSLETTER_FIELD = "NewsletterFrequency"
TOPICS_FIELD = "AlertTopics"
COUNTRIES_FIELD = "AlertCountries"
INSTITUTIONS_FIELD = "AlertInstitutions"
ALERT_FIELDS = (TOPICS_FIELD, COUNTRIES_FIELD, INSTITUTIONS_FIELD)


def topic_token(topic):
    return f"t:{slugify(topic)}"


def country_token(code):
    return f"c:{code}"


def university_token(pk):
    return f"u:{pk}"


def _join(tokens):
    tokens = sorted(set(tokens))
    return f"|{'|'.join(tokens)}|" if tokens else ""


def alert_field_values(profile):
    """The three alert custom-field values for ``profile``."""
    return {
        TOPICS_FIELD: _join(topic_token(t) for t in profile.alert_topics or []),
        COUNTRIES_FIELD: _join(country_token(c) for c in profile.alert_countries or []),
        INSTITUTIONS_FIELD: _join(university_token(u) for u in profile.alert_universities or []),
    }


def desired_state(profile):
    """What CM should hold for ``profile``: ``newsletter`` / ``alerts`` are the custom
    fields for that list, or ``None`` when the member should not be on it."""
    user = profile.user
    active = user.is_active
    freq = profile.newsletter_frequency
    alerts = alert_field_values(profile)
    return {
        "email": user.email,
        "name": user.get_full_name(),
        "newsletter": ({NEWSLETTER_FIELD: freq}
                       if active and freq != profile.NewsletterFrequency.OFF else None),
        "alerts": alerts if active and any(alerts.values()) else None,
    }


def state_hash(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def _unsubscribe_quietly(client, list_id, email):
    try:
        client.unsubscribe(list_id, email)
    except CampaignMonitorError as exc:
        # 203 = "email address is not on this list" -- already the desired state.
        if exc.code != 203:
            raise


def _apply(client, state, previous_email="", resubscribe=()):
    """Push ``state`` to both lists.

    A member who unsubscribed in CM must stay unsubscribed -- even if our webhook
    missed it -- so a routine sync never resubscribes; only the lists named in
    ``resubscribe`` (set when the member saves that list's settings) do."""
    lists = [("newsletter", cm_lists.list_id(cm_lists.NEWSLETTER)),
             ("alerts", cm_lists.list_id(cm_lists.ALERTS))]
    for key, list_id in lists:
        fields = state[key]
        # The member changed their email: the old address must stop receiving.
        if previous_email and previous_email != state["email"]:
            _unsubscribe_quietly(client, list_id, previous_email)
        if fields is None:
            _unsubscribe_quietly(client, list_id, state["email"])
        else:
            client.upsert_subscriber(list_id, state["email"], state["name"], fields,
                                     resubscribe=key in resubscribe)


def sync_profile(profile, client=None, force=False):
    """Push ``profile``'s state to CM. Returns True if a sync was performed.

    Never raises on a CM failure: it is logged and the stored hash is left stale,
    so the nightly ``cm_sync`` retries. Preference saves must not fail because CM
    is down.
    """
    if not is_configured() or not cm_lists.provisioned():
        return False
    state = desired_state(profile)
    new_hash = state_hash(state)
    if not force and profile.cm_synced_state == new_hash:
        return False
    if (not profile.cm_synced_state and state["newsletter"] is None
            and state["alerts"] is None):
        # Never pushed and wants nothing: record that, skip two pointless API calls
        # (this is most members when CM is first backfilled).
        type(profile).objects.filter(pk=profile.pk).update(
            cm_synced_state=new_hash, cm_synced_email=state["email"])
        profile.cm_synced_state, profile.cm_synced_email = new_hash, state["email"]
        return True
    try:
        _apply(client or CampaignMonitorClient(), state, profile.cm_synced_email,
               resubscribe=getattr(profile, "cm_resubscribe", ()))
    except CampaignMonitorError:
        logger.exception("Campaign Monitor sync failed for profile %s", profile.pk)
        return False
    type(profile).objects.filter(pk=profile.pk).update(
        cm_synced_state=new_hash, cm_synced_email=state["email"])
    profile.cm_synced_state = new_hash
    profile.cm_synced_email = state["email"]
    return True


def queue_sync(profile):
    """Sync after the surrounding transaction commits (no-op when unchanged)."""
    if not is_configured() or not cm_lists.provisioned():
        return
    if profile.cm_synced_state == state_hash(desired_state(profile)):
        return
    transaction.on_commit(lambda: sync_profile(profile))
