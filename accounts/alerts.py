"""Email alert helpers.

A member can subscribe to specific paper topics, visit countries and visit institutions
in Settings (Profile.alert_topics / alert_countries / alert_universities). Once a week,
send_alerts.py emails each subscriber the approved papers and visits posted
since their last alert that match what they picked. With Campaign Monitor
configured the alerts go out as one campaign instead (accounts.campaigns); this
module is the per-user fallback for environments without it.
"""
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from accounts.cm_sync import alert_field_values, country_token, topic_token, university_token
from core.email import attach_logo, cm_headers, default_reply_to
from core.links import absolute_url
from publications.models import Publication
from seminars.models import Seminar

UNSUBSCRIBE_SALT = "accounts.alerts.unsubscribe"

# Alerts are weekly only -- there's no monthly cohort to choose between.
ALERT_WINDOW = timedelta(days=7)


def publication_item(pub):
    """Item dict for one approved publication."""
    return {
        "title": pub.title,
        "url": absolute_url(reverse("publication_detail", kwargs={"pk": pub.pk})),
        "meta": pub.get_country_code_display() if pub.country_code else "",
        "authors": ", ".join(str(author) for author in pub.ordered_authors),
        "abstract": pub.abstract,
    }


def visit_item(visit):
    """Item dict for one approved visit."""
    return {
        "title": str(visit),
        "url": absolute_url(visit.get_absolute_url()),
        "meta": ", ".join(visit.country_labels()),
    }


def make_unsubscribe_token(user):
    """Return a signed, tamper-proof token identifying ``user``.

    A separate salt from the newsletter's unsubscribe token means a newsletter
    link can never be replayed to also turn off alerts (or vice versa).
    """
    return signing.dumps({"uid": user.pk}, salt=UNSUBSCRIBE_SALT)


def read_unsubscribe_token(token, max_age=None):
    """Return the user id encoded in ``token`` or ``None`` if invalid."""
    try:
        data = signing.loads(token, salt=UNSUBSCRIBE_SALT, max_age=max_age)
    except signing.BadSignature:
        return None
    return data.get("uid")


def default_since(now=None):
    """First-run look-back start, before ``last_alert_sent_at`` is set."""
    now = now or timezone.now()
    return now - ALERT_WINDOW


def _posted_since(since, submitted_field):
    """Rows that went public since ``since``.

    Keyed on approval time, not submission time: an item submitted just before
    a send but approved just after would otherwise fall between two windows and
    never be alerted. Rows approved without ``reviewed_at`` (e.g. via the admin
    Status dropdown) fall back to the submission date.
    """
    return Q(reviewed_at__gte=since) | Q(
        reviewed_at__isnull=True, **{f"{submitted_field}__gte": since})


def week_items(since):
    """The papers and visits that went public since ``since``, each with the set
    of interest tokens (accounts.cm_sync) that make it relevant to a subscriber.

    Matching is done in Python over the week's approved rows (a small set)
    rather than a JSON-contains query, which would behave differently on
    SQLite vs. the MariaDB used in production. Returns ``(publications, visits)``
    as lists of ``(item_dict, tokens)``.
    """
    publications = [
        (publication_item(pub), {topic_token(t) for t in pub.topic or []})
        for pub in (
            Publication.objects.filter(status="approved")
            .filter(_posted_since(since, "applied_at"))
            .prefetch_related("author_links__author__user")
            .order_by("-applied_at")
        )
    ]
    visits = []
    for visit in (
        Seminar.objects.approved().filter(_posted_since(since, "created_at"))
        .select_related("university")
        .order_by("-created_at")
    ):
        tokens = {country_token(c) for c in visit.countries or []}
        if visit.university_id:
            tokens.add(university_token(visit.university_id))
        visits.append((visit_item(visit), tokens))
    return publications, visits


def profile_tokens(profile):
    """Every interest token ``profile`` follows."""
    tokens = set()
    for value in alert_field_values(profile).values():
        tokens.update(t for t in value.split("|") if t)
    return tokens


def collect_alert_matches(profile, since):
    """Return the non-empty alert sections for ``profile`` since ``since``."""
    followed = profile_tokens(profile)
    publications, visits = week_items(since)
    sections = []

    matched = [item for item, tokens in publications if followed & tokens]
    if matched:
        sections.append({
            "key": "publications",
            "label": "New papers matching your topics",
            "items": matched,
        })

    matched = [item for item, tokens in visits if followed & tokens]
    if matched:
        sections.append({
            "key": "visits",
            "label": "New visits matching your alerts",
            "items": matched,
        })

    return sections


def build_alert_email(user, sections):
    """Render the subject/text/html for an alert email to ``user``.

    Also returns the unsubscribe URL so the caller can set a
    List-Unsubscribe header without recomputing (and re-signing) the token.
    """
    total = sum(len(section["items"]) for section in sections)
    unsubscribe_url = absolute_url(
        reverse("alerts_unsubscribe",
                kwargs={"token": make_unsubscribe_token(user)})
    )
    context = {
        "user": user,
        "sections": sections,
        "total": total,
        "site_url": settings.SITE_URL.rstrip("/"),
        "manage_url": absolute_url(reverse("settings")),
        "unsubscribe_url": unsubscribe_url,
    }
    subject = "Labor Hub alerts: {} new match{}".format(
        total, "" if total == 1 else "es")
    text_body = render_to_string("emails/alerts.txt", context)
    html_body = render_to_string("emails/alerts.html", context)
    return subject, text_body, html_body, unsubscribe_url


def send_user_alerts(user, now=None, connection=None):
    """Send ``user`` an alert email for matches since their last one.

    Returns ``True`` when an email was sent, ``False`` when skipped because
    no topics/countries/institutions are set or there were no matches. ``connection`` lets
    send_alerts reuse a single SMTP connection across the whole cohort,
    so the cohort is one connection, not one per member.
    """
    now = now or timezone.now()
    profile = user.profile

    if not (profile.alert_topics or profile.alert_countries or profile.alert_universities):
        return False

    since = profile.last_alert_sent_at or default_since(now)
    sections = collect_alert_matches(profile, since)
    if not sections:
        return False

    subject, text_body, html_body, unsubscribe_url = build_alert_email(user, sections)
    headers = cm_headers(track_opens=True)
    headers["List-Unsubscribe"] = f"<{unsubscribe_url}>"
    message = EmailMultiAlternatives(
        subject, text_body, from_email=settings.CAMPAIGN_FROM_EMAIL, to=[user.email],
        reply_to=default_reply_to(), headers=headers, connection=connection,
    )
    message.attach_alternative(html_body, "text/html")
    attach_logo(message)
    # This runs unattended from cron across every subscriber in one pass, so one
    # bad address must not abort the rest of the cohort.
    sent = message.send(fail_silently=True)

    if not sent:
        return False

    profile.last_alert_sent_at = now
    profile.save(update_fields=["last_alert_sent_at"])
    return True
