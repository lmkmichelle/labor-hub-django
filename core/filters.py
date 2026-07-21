"""Shared query-parameter parsing for list-page sidebar filters.

The Tagify pill inputs used across the site submit their value either as a JSON
array (``[{"value": "US"}, ...]``) or as a plain comma-separated string. These
helpers normalise both shapes into a de-duplicated list of terms and, for
country pickers, resolve those terms to ISO country codes from
``COUNTRY_CHOICES``. The logic mirrors the country handling in the jobs and
seminars views so every list page filters countries the same way.
"""
import json

from core.constants import COUNTRY_CHOICES

_AVAILABLE_CODES = {code for code, _ in COUNTRY_CHOICES}


def parse_pill_terms(raw_value):
    """Normalise a Tagify pill value (JSON array or comma list) into terms."""
    raw_value = (raw_value or "").strip()
    if not raw_value:
        return []

    parsed_terms = []
    if raw_value.startswith("["):
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        value = str(item.get("value", "")).strip()
                    else:
                        value = str(item).strip()
                    if value:
                        parsed_terms.append(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed_terms = []

    if not parsed_terms:
        parsed_terms = [part.strip() for part in raw_value.split(",") if part.strip()]

    deduped_terms = []
    seen = set()
    for term in parsed_terms:
        lowered = term.lower()
        if lowered not in seen:
            seen.add(lowered)
            deduped_terms.append(term)
    return deduped_terms


def map_country_terms_to_codes(terms):
    """Resolve free-text country terms (names or ISO codes) to ISO codes."""
    if not terms:
        return []

    selected_codes = []
    seen = set()
    for term in terms:
        normalized = term.strip().lower()
        upper_term = term.strip().upper()

        if upper_term in _AVAILABLE_CODES and upper_term not in seen:
            seen.add(upper_term)
            selected_codes.append(upper_term)
            continue

        for code, label in COUNTRY_CHOICES:
            if normalized == label.lower() or normalized in label.lower():
                if code not in seen:
                    seen.add(code)
                    selected_codes.append(code)
    return selected_codes
