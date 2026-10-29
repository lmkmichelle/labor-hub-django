"""The Labor Hub newsletter: live listings around hand-written issue text.

``newsletter_context`` pulls what is open right now (events, special issues and
jobs by deadline, the most downloaded discussion papers) and wraps it in the
intro and "coming next week" text below. Edit ``ISSUE`` for each issue; the
issue number and date fill in themselves.
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from accounts.digests import absolute_url
from core.models import EmailCampaign
from events.models import Event
from jobs.models import Job
from publications.models import Publication
from special_issues.models import SpecialIssue

# -- Per-issue text: edit before each send ----------------------------------
ISSUE = {
    "welcome": "Thank you for joining the community. We look forward to your contributions!",
    "visits": ("Several members have posted upcoming visits, and some are open to extending "
               "their trips for seminars. Check who is coming to your region."),
    "next_title": "Job Market Papers",
    "next_body": ("We'll launch a special page listing all the job market papers we have "
                  "received, a great way to discover this year's candidates."),
    "next_note": "Students on the market can still join the Hub, with sign-off from their advisor.",
}

MAX_LISTED = 6
MAX_PAPERS = 5


def _deadline_label(day, today):
    if day == today:
        return "Deadline today"
    if day == today + timedelta(days=1):
        return f"Deadline tomorrow, {day:%b}. {day.day}"
    return f"Deadline: {day:%b}. {day.day}, {day.year}"


def issue_number():
    return EmailCampaign.objects.filter(
        kind=EmailCampaign.Kind.NEWSLETTER, status=EmailCampaign.Status.SENT).count() + 1


def newsletter_context(now=None):
    now = now or timezone.now()
    today = timezone.localdate(now)
    url = lambda name, **kw: absolute_url(reverse(name, kwargs=kw))  # noqa: E731

    events = []
    for event in (Event.objects.filter(status="approved", deadline__isnull=False,
                                       deadline__gte=now - timedelta(days=1))
                  .order_by("deadline")):
        day = timezone.localtime(event.deadline).date()
        if day < today:
            continue
        place = f" · {event.location}" if event.location else ""
        events.append({
            "title": event.title, "url": url("event-detail", pk=event.pk),
            "meta": f"{event.get_category_display()}{place} · {event.date:%B} {event.date.day}, {event.date.year}",
            "deadline": _deadline_label(day, today),
        })

    special_issues = [{
        "title": si.title, "url": url("special-issue-detail", pk=si.pk), "meta": si.journal,
        "deadline": _deadline_label(si.submission_deadline, today),
    } for si in SpecialIssue.objects.filter(status="approved", submission_deadline__gte=today)
        .order_by("submission_deadline")]

    jobs = [{
        "title": job.title, "url": url("job-detail", pk=job.pk),
        "meta": " · ".join(x for x in [job.employer, ", ".join(job.country_labels())] if x),
        "deadline": _deadline_label(job.deadline, today),
    } for job in Job.objects.filter(status="approved", deadline__gte=today).order_by("deadline")]

    papers = [{
        "rank": i, "title": p.title, "url": url("publication_detail", pk=p.pk),
        "download_url": url("publication_download", pk=p.pk),
        "authors": ", ".join(str(a) for a in p.ordered_authors),
    } for i, p in enumerate(Publication.most_downloaded(MAX_PAPERS), start=1)]

    return {
        "issue": ISSUE,
        "issue_number": issue_number(),
        "issue_date": now,
        "events": events[:MAX_LISTED],
        "special_issues": special_issues[:MAX_LISTED],
        "jobs": jobs[:MAX_LISTED],
        "papers": papers,
        "site_url": settings.SITE_URL.rstrip("/"),
        "logo_src": absolute_url(static("images/logo.png")),
        "urls": {
            "login": url("login"), "announcements": url("announcements"),
            "events": url("events-list"), "special_issues": url("special-issues-list"),
            "jobs": url("jobs-list"), "visits": url("seminars-list"),
            "papers": absolute_url(reverse("publications")) + "?type=discussion",
            "membership": url("membership"), "contact": url("contact"), "faq": url("faq"),
            "settings": url("settings"),
        },
    }


def render_newsletter(context):
    from django.template.loader import render_to_string
    return (render_to_string("emails/newsletter.html", context),
            render_to_string("emails/newsletter.txt", context))


def create_newsletter_campaign(now=None):
    """Render this issue and store the snapshot CM will fetch. Not sent yet."""
    now = now or timezone.now()
    context = newsletter_context(now)
    html, text = render_newsletter(context)
    last = EmailCampaign.objects.filter(
        kind=EmailCampaign.Kind.NEWSLETTER, status=EmailCampaign.Status.SENT).first()
    return EmailCampaign.objects.create(
        kind=EmailCampaign.Kind.NEWSLETTER,
        subject=f"The Labor Hub Newsletter No. {context['issue_number']}",
        html=html, text=text,
        period_start=last.period_end if last else now, period_end=now,
    )
