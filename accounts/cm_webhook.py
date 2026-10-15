"""Campaign Monitor list webhook: mirror unsubscribes/bounces/complaints into the app.

A ``Deactivate`` event on the digest list turns the member's digest off; on the
alerts list it clears their topic/country/institution alerts. Members are matched
by email. Uses ``QuerySet.update`` so the change does not echo back to CM through
the Profile signal.
"""
import hmac
import json

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts import cm_sync
from accounts.models import Profile


def _deactivate(list_id, email):
    profiles = Profile.objects.filter(user__email__iexact=email)
    if list_id == settings.CM_DIGEST_LIST_ID:
        profiles.update(digest_frequency=Profile.DigestFrequency.OFF)
    elif list_id == settings.CM_ALERT_LIST_ID:
        profiles.update(alert_topics=[], alert_countries=[], alert_universities=[])
    else:
        return
    # CM already holds the new state; record it so cm_sync doesn't re-push.
    for profile in profiles.select_related("user"):
        profiles.filter(pk=profile.pk).update(
            cm_synced_state=cm_sync.state_hash(cm_sync.desired_state(profile)))


@csrf_exempt
@require_POST
def cm_webhook(request, secret):
    expected = settings.CM_WEBHOOK_SECRET
    if not expected or not hmac.compare_digest(secret.encode(), expected.encode()):
        raise Http404
    try:
        payload = json.loads(request.body)
        list_id = payload["ListID"]
        events = payload.get("Events", [])
    except (ValueError, KeyError, TypeError):
        return HttpResponseBadRequest("bad payload")
    for event in events:
        if event.get("Type") == "Deactivate" and event.get("EmailAddress"):
            _deactivate(list_id, event["EmailAddress"])
    return HttpResponse(status=204)
