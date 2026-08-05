"""Email digest helpers.

Collects recently added, publicly visible content and turns it into a
plain-text + HTML digest email. Used by the ``send_digests`` management
command (run from cron on the host) and covered directly by unit tests.
"""
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from events.models import Event
from jobs.models import Job
from publications.models import Publication
from seminars.models import Seminar

UNSUBSCRIBE_SALT = "accounts.digests.unsubscribe"

# Look-back window used the first time a user is sent a digest (before
# ``last_digest_sent_at`` is set).
FREQUENCY_WINDOWS = {
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
}


def absolute_url(path):
    """Prefix a root-relative path with the configured public site URL."""
    return "{}{}".format(settings.SITE_URL.rstrip("/"), path)


def make_unsubscribe_token(user):
    """Return a signed, tamper-proof token identifying ``user``."""
    return signing.dumps({"uid": user.pk}, salt=UNSUBSCRIBE_SALT)


def read_unsubscribe_token(token, max_age=None):
    """Return the user id encoded in ``token`` or ``None`` if invalid."""
    try:
        data = signing.loads(token, salt=UNSUBSCRIBE_SALT, max_age=max_age)
    except signing.BadSignature:
        return None
    return data.get("uid")


def default_since(frequency, now=None):
    """First-run look-back start for a frequency cohort."""
    now = now or timezone.now()
    window = FREQUENCY_WINDOWS.get(frequency, FREQUENCY_WINDOWS["weekly"])
    return now - window


def collect_new_content(since):
    """Return the non-empty digest sections for content added after ``since``.

    Only publicly visible (approved) content is included: publications, events,
    jobs, and visits all go through the same moderation step before appearing.
    """
    sections = []

    publications = list(
        Publication.objects.filter(status="approved", applied_at__gte=since)
        .order_by("-applied_at")
    )
    if publications:
        sections.append({
            "key": "publications",
            "label": "New discussion papers",
            "items": [
                {
                    "title": pub.title,
                    "url": absolute_url(
                        reverse("publication_detail", kwargs={"pk": pub.pk})
                    ),
                    "meta": pub.get_country_code_display() if pub.country_code else "",
                }
                for pub in publications
            ],
        })

    events = list(
        Event.objects.filter(status="approved", created_at__gte=since)
        .order_by("-created_at")
    )
    if events:
        sections.append({
            "key": "events",
            "label": "New events",
            "items": [
                {
                    "title": event.title,
                    "url": absolute_url(
                        reverse("event-detail", kwargs={"pk": event.pk})
                    ),
                    "meta": event.location,
                }
                for event in events
            ],
        })

    jobs = list(Job.objects.approved().filter(created_at__gte=since).order_by("-created_at"))
    if jobs:
        sections.append({
            "key": "jobs",
            "label": "New job openings",
            "items": [
                {
                    "title": job.title,
                    "url": absolute_url(job.get_absolute_url()),
                    "meta": ", ".join(job.country_labels()),
                }
                for job in jobs
            ],
        })

    visits = list(Seminar.objects.approved().filter(created_at__gte=since).order_by("-created_at"))
    if visits:
        sections.append({
            "key": "visits",
            "label": "New visits",
            "items": [
                {
                    "title": str(visit),
                    "url": absolute_url(visit.get_absolute_url()),
                    "meta": ", ".join(visit.country_labels()),
                }
                for visit in visits
            ],
        })

    return sections


def build_digest_email(user, sections):
    """Render the subject/text/html for a digest to ``user``."""
    total = sum(len(section["items"]) for section in sections)
    context = {
        "user": user,
        "sections": sections,
        "total": total,
        "site_url": settings.SITE_URL.rstrip("/"),
        "manage_url": absolute_url(reverse("edit_profile")),
        "unsubscribe_url": absolute_url(
            reverse("digest_unsubscribe",
                    kwargs={"token": make_unsubscribe_token(user)})
        ),
    }
    subject = "Labor Hub: {} new update{}".format(total, "" if total == 1 else "s")
    text_body = render_to_string("emails/digest.txt", context)
    html_body = render_to_string("emails/digest.html", context)
    return subject, text_body, html_body


def send_user_digest(user, now=None):
    """Send ``user`` a digest of content since their last one.

    Returns ``True`` when an email was sent, ``False`` when skipped because
    the digest is disabled or there was nothing new.
    """
    now = now or timezone.now()
    profile = user.profile

    if profile.digest_frequency == profile.DigestFrequency.OFF:
        return False

    since = profile.last_digest_sent_at or default_since(
        profile.digest_frequency, now
    )
    sections = collect_new_content(since)
    if not sections:
        return False

    subject, text_body, html_body = build_digest_email(user, sections)
    message = EmailMultiAlternatives(subject, text_body, to=[user.email])
    message.attach_alternative(html_body, "text/html")
    message.send()

    profile.last_digest_sent_at = now
    profile.save(update_fields=["last_digest_sent_at"])
    return True
