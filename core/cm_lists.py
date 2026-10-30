"""Which Campaign Monitor lists this site uses, found by name instead of configured.

``cm_setup`` creates the two lists (Newsletter, Alerts) and stores their ids in
``CampaignMonitorResource``; everything else asks ``list_id()``. A
``CM_NEWSLETTER_LIST_ID`` / ``CM_ALERT_LIST_ID`` setting still wins when set, which
is what the tests use and an escape hatch for an account with several lists of the
same name.
"""
from django.conf import settings

NEWSLETTER = "newsletter"
ALERTS = "alerts"
TITLES = {NEWSLETTER: "Labor Hub Newsletter", ALERTS: "Labor Hub Alerts"}
_SETTING = {NEWSLETTER: "CM_NEWSLETTER_LIST_ID", ALERTS: "CM_ALERT_LIST_ID"}


def stored(key):
    """What ``cm_setup`` recorded under ``key`` (a list id, or a done-marker)."""
    from core.models import CampaignMonitorResource
    row = CampaignMonitorResource.objects.filter(key=key).first()
    return row.cm_id if row else ""


def list_id(key):
    """The CM list id for ``key``, or ``""`` when ``cm_setup`` hasn't run yet."""
    return getattr(settings, _SETTING[key], "") or stored(key)


def provisioned():
    """Both lists are known, so members can be pushed to them."""
    return bool(list_id(NEWSLETTER) and list_id(ALERTS))


def remember(key, cm_id):
    from core.models import CampaignMonitorResource
    CampaignMonitorResource.objects.update_or_create(key=key, defaults={"cm_id": cm_id})
