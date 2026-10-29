"""Keep Campaign Monitor (CM) subscriber lists in step with member preferences.

Digests and alerts are CM *campaigns*, sent to list segments. A member is on the
digest list when ``digest_frequency`` is weekly/monthly, and on the alerts list
when any alert topic/country/institution is set. Alert interests are stored in
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

from core.campaign_monitor import CampaignMonitorClient, CampaignMonitorError, is_configured

logger = logging.getLogger(__name__)

DIGEST_FIELD = "DigestFrequency"
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
    """What CM should hold for ``profile``: ``digest`` / ``alerts`` are the custom
    fields for that list, or ``None`` when the member should not be on it."""
    user = profile.user
    active = user.is_active
    freq = profile.digest_frequency
    alerts = alert_field_values(profile)
    return {
        "email": user.email,
        "name": user.get_full_name(),
        # Every active member is on the newsletter list (no custom fields).
        "members": {} if active and settings.CM_MEMBERS_LIST_ID else None,
        "digest": {DIGEST_FIELD: freq} if active and freq != profile.DigestFrequency.OFF else None,
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


def _apply(client, state, previous_email=""):
    lists = [("digest", settings.CM_DIGEST_LIST_ID), ("alerts", settings.CM_ALERT_LIST_ID)]
    if settings.CM_MEMBERS_LIST_ID:
        lists.append(("members", settings.CM_MEMBERS_LIST_ID))
    for key, list_id in lists:
        fields = state[key]
        # The member changed their email: the old address must stop receiving.
        if previous_email and previous_email != state["email"]:
            _unsubscribe_quietly(client, list_id, previous_email)
        if fields is None:
            _unsubscribe_quietly(client, list_id, state["email"])
        else:
            # Members who unsubscribed from the newsletter in CM must stay out,
            # so a later name/email sync never resubscribes them.
            client.upsert_subscriber(list_id, state["email"], state["name"], fields,
                                     resubscribe=(key != "members"))


def sync_member_to_newsletter_list(profile, client):
    """Put one active member on the newsletter list and nothing else.

    For `cm_sync --members-only`: the newsletter can go out before digests and alerts
    are moved to Campaign Monitor. Never resubscribes anyone who left the list.
    Returns True if the member was pushed."""
    state = desired_state(profile)
    if state["members"] is None:
        return False
    client.upsert_subscriber(settings.CM_MEMBERS_LIST_ID, state["email"], state["name"],
                             state["members"], resubscribe=False)
    return True


def sync_profile(profile, client=None, force=False):
    """Push ``profile``'s state to CM. Returns True if a sync was performed.

    Never raises on a CM failure: it is logged and the stored hash is left stale,
    so the nightly ``cm_sync`` retries. Preference saves must not fail because CM
    is down.
    """
    if not is_configured():
        return False
    state = desired_state(profile)
    new_hash = state_hash(state)
    if not force and profile.cm_synced_state == new_hash:
        return False
    if (not profile.cm_synced_state and state["digest"] is None
            and state["alerts"] is None and state["members"] is None):
        # Never pushed and wants nothing: record that, skip two pointless API calls
        # (this is most members when CM is first backfilled).
        type(profile).objects.filter(pk=profile.pk).update(
            cm_synced_state=new_hash, cm_synced_email=state["email"])
        profile.cm_synced_state, profile.cm_synced_email = new_hash, state["email"]
        return True
    try:
        _apply(client or CampaignMonitorClient(), state, profile.cm_synced_email)
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
    if not is_configured():
        return
    if profile.cm_synced_state == state_hash(desired_state(profile)):
        return
    transaction.on_commit(lambda: sync_profile(profile))
