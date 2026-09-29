"""Shared client for the Hipolabs public universities API.

Used by both ``import_universities`` (the Upsun deploy-hook bulk import) and
``seminars.views.universities_by_country`` (the picker's live fallback for a
country with no rows yet), so the request shape -- and the one fact about it
that matters, that it only listens on plain HTTP -- lives in exactly one
place.
"""
import json
from urllib.parse import urlencode
from urllib.request import urlopen

# hipolabs' API only listens on plain HTTP -- port 443 refuses the connection
# outright (confirmed both locally and from Upsun; this isn't an Upsun egress
# restriction). The payload is a public, unauthenticated university directory
# with no sensitive data, so the lack of transport encryption here isn't a
# real risk.
BASE_URL = 'http://universities.hipolabs.com/search'


def fetch_universities(country_name='', timeout=30):
    """Fetch the raw university rows for a country name (or all, if blank).

    Returns a list of dicts shaped like the Hipolabs API response
    (``name``, ``country``, ``alpha_two_code``, ``web_pages``, ``domains``),
    filtered down to just the dict rows.

    Raises on a network failure or an unparsable/unexpected payload -- callers
    that want a fallback-to-empty behaviour (the picker's live lookup) catch
    around this; the bulk-import command instead lets it propagate as a
    ``CommandError`` so a broken fetch surfaces loudly instead of silently
    importing nothing.
    """
    country_name = (country_name or '').strip()
    url = BASE_URL
    if country_name:
        url = f"{url}?{urlencode({'country': country_name})}"

    with urlopen(url, timeout=timeout) as response:
        payload = response.read().decode('utf-8')

    rows = json.loads(payload)
    if not isinstance(rows, list):
        raise ValueError('Unexpected universities API response format.')
    return [row for row in rows if isinstance(row, dict)]
