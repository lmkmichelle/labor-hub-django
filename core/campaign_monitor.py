"""Thin Campaign Monitor (createsend) REST v3.3 client.

Stdlib only (``urllib``), so it adds no dependency. Digests and alerts are
campaigns under CM's terms of service; this module manages the subscriber lists,
segments and campaigns they need. Authentication is HTTP Basic with the API key
as the username and a dummy password, per the CM docs. The key is never logged.
"""
import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

API_ROOT = "https://api.createsend.com/api/v3.3"
TIMEOUT = 20


class CampaignMonitorError(Exception):
    """Raised for any non-2xx response or transport failure."""

    def __init__(self, message, status=None, code=None):
        super().__init__(message)
        self.status = status
        self.code = code


def is_configured():
    return settings.CAMPAIGN_DELIVERY == "cm"


class CampaignMonitorClient:
    def __init__(self, api_key=None, client_id=None):
        self.api_key = api_key or settings.CM_API_KEY
        self.client_id = client_id or settings.CM_CLIENT_ID

    # -- transport ---------------------------------------------------------
    def _request(self, method, path, body=None, params=None):
        url = f"{API_ROOT}/{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        token = base64.b64encode(f"{self.api_key}:x".encode()).decode()
        request = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json; charset=utf-8",
        })
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = {}
            try:
                detail = json.loads(exc.read() or b"{}")
            except ValueError:
                pass
            raise CampaignMonitorError(
                detail.get("Message") or f"HTTP {exc.code} from Campaign Monitor",
                status=exc.code, code=detail.get("Code"),
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise CampaignMonitorError(f"Campaign Monitor unreachable: {exc}") from None
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return raw.decode()

    # -- lists & custom fields ---------------------------------------------
    def create_list(self, title, unsubscribe_page="", confirmed_opt_in=False):
        return self._request("POST", f"lists/{self.client_id}.json", {
            "Title": title,
            "UnsubscribePage": unsubscribe_page,
            "ConfirmedOptIn": confirmed_opt_in,
            "UnsubscribeSetting": "OnlyThisList",
        })

    def lists(self):
        return self._request("GET", f"clients/{self.client_id}/lists.json")

    def create_custom_field(self, list_id, name, data_type="Text"):
        return self._request("POST", f"lists/{list_id}/customfields.json", {
            "FieldName": name, "DataType": data_type,
        })

    def custom_fields(self, list_id):
        return self._request("GET", f"lists/{list_id}/customfields.json")

    # -- subscribers -------------------------------------------------------
    def upsert_subscriber(self, list_id, email, name, custom_fields=None, resubscribe=True):
        """Add the subscriber, or update them (and resubscribe) if they exist."""
        return self._request("POST", f"subscribers/{list_id}.json", {
            "EmailAddress": email,
            "Name": name,
            "CustomFields": [{"Key": k, "Value": v} for k, v in (custom_fields or {}).items()],
            "ConsentToTrack": "Yes",
            "Resubscribe": resubscribe,
            "RestartSubscriptionBasedAutoresponders": False,
        })

    def unsubscribe(self, list_id, email):
        return self._request("POST", f"subscribers/{list_id}/unsubscribe.json",
                             {"EmailAddress": email})

    def delete_subscriber(self, list_id, email):
        return self._request("DELETE", f"subscribers/{list_id}.json", params={"email": email})

    def active_subscribers(self, list_id, page=1, page_size=1000):
        return self._request("GET", f"lists/{list_id}/active.json",
                             params={"page": page, "pagesize": page_size})

    # -- segments ----------------------------------------------------------
    def create_segment(self, list_id, title, rule_groups):
        """``rule_groups``: list of lists of ``(RuleType, Clause)`` tuples. Groups
        are ANDed, the rules inside a group are ORed."""
        return self._request("POST", f"segments/{list_id}.json", {
            "Title": title,
            "RuleGroups": [
                {"Rules": [{"RuleType": rt, "Clause": clause} for rt, clause in group]}
                for group in rule_groups
            ],
        })

    def segments(self, list_id):
        return self._request("GET", f"lists/{list_id}/segments.json")

    def delete_segment(self, segment_id):
        return self._request("DELETE", f"segments/{segment_id}.json")

    # -- campaigns ---------------------------------------------------------
    def create_campaign(self, *, name, subject, html_url, text_url="",
                        list_ids=(), segment_ids=(), from_name, from_email, reply_to):
        return self._request("POST", f"campaigns/{self.client_id}.json", {
            "Subject": subject,
            "Name": name,
            "FromName": from_name,
            "FromEmail": from_email,
            "ReplyTo": reply_to,
            "HtmlUrl": html_url,
            "TextUrl": text_url,
            "ListIDs": list(list_ids),
            "SegmentIDs": list(segment_ids),
        })

    def send_campaign(self, campaign_id, confirmation_email, send_date="Immediately"):
        return self._request("POST", f"campaigns/{campaign_id}/send.json", {
            "ConfirmationEmail": confirmation_email,
            "SendDate": send_date,
        })

    def send_preview(self, campaign_id, recipients, personalize="Fallback"):
        return self._request("POST", f"campaigns/{campaign_id}/sendpreview.json", {
            "PreviewRecipients": list(recipients),
            "Personalize": personalize,
        })

    # -- webhooks ----------------------------------------------------------
    def create_webhook(self, list_id, url, events=("Subscribe", "Deactivate", "Update")):
        return self._request("POST", f"lists/{list_id}/webhooks.json", {
            "Events": list(events), "Url": url, "PayloadFormat": "json",
        })

    def webhooks(self, list_id):
        return self._request("GET", f"lists/{list_id}/webhooks.json")
