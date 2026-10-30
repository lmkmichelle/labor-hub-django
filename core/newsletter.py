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

from core.links import absolute_url
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

WEEKLY, MONTHLY = "weekly", "monthly"
# Per newsletter: the stored campaign kind, its Campaign Monitor segment, how far back
# the papers ranking looks when there is no earlier issue, how soon after a send the
# scheduled run stays quiet (so a manual send is not followed by a duplicate), and the
# wording for the period.
KINDS = {
    WEEKLY: {
        "campaign_kind": EmailCampaign.Kind.NEWSLETTER, "segment": "Newsletter weekly",
        "window": timedelta(days=7), "guard": timedelta(days=6),
        "this_period": "This week", "label": "Weekly",
    },
    MONTHLY: {
        "campaign_kind": EmailCampaign.Kind.NEWSLETTER_MONTHLY, "segment": "Newsletter monthly",
        "window": timedelta(days=30), "guard": timedelta(days=20),
        "this_period": "This month", "label": "Monthly",
    },
}


def _deadline_label(day, today):
    if day == today:
        return "Deadline today"
    if day == today + timedelta(days=1):
        return f"Deadline tomorrow, {day:%b}. {day.day}"
    return f"Deadline: {day:%b}. {day.day}, {day.year}"


def last_sent_issue(kind=WEEKLY):
    return EmailCampaign.objects.filter(
        kind=KINDS[kind]["campaign_kind"], status=EmailCampaign.Status.SENT).first()


def issue_number(kind=WEEKLY):
    return EmailCampaign.objects.filter(
        kind=KINDS[kind]["campaign_kind"], status=EmailCampaign.Status.SENT).count() + 1


def period_start(kind=WEEKLY, now=None):
    """Where this issue's download ranking starts: the previous issue of the same
    kind, or the default window back from ``now`` for the first one."""
    now = now or timezone.now()
    last = last_sent_issue(kind)
    if last:
        return last.sent_at or last.period_end
    return now - KINDS[kind]["window"]


def newsletter_context(kind=WEEKLY, now=None):
    now = now or timezone.now()
    today = timezone.localdate(now)
    number = issue_number(kind)
    spec = KINDS[kind]
    first_issue = kind == WEEKLY and number == 1
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

    # The first weekly issue ranks all-time: the timestamped log only began shortly
    # before it. Later issues rank the downloads since the previous issue of the same
    # kind; a quiet period falls back to all-time rather than drop the section.
    since = period_start(kind, now)
    ranked = [] if first_issue else list(Publication.most_downloaded(MAX_PAPERS, since=since))
    all_time = not ranked
    papers_heading = f"Most downloaded papers {spec['this_period'].lower()}"
    if all_time:
        ranked = list(Publication.most_downloaded(MAX_PAPERS))
        papers_heading = "Most downloaded papers"
    papers = [{
        "rank": i, "title": p.title, "url": url("publication_detail", pk=p.pk),
        "download_url": url("publication_download", pk=p.pk),
        "authors": ", ".join(str(a) for a in p.ordered_authors),
        # Not shown in the email; the admin's preview lists them.
        "downloads": p.download_count if all_time else p.recent,
        "all_time": p.download_count,
    } for i, p in enumerate(ranked, start=1)]

    if kind == MONTHLY:
        local = timezone.localtime(now)
        subject = f"The Labor Hub Monthly Newsletter, {local:%B} {local.year}"
    else:
        subject = f"The Labor Hub Newsletter No. {number}"

    return {
        "issue": ISSUE,
        "kind": kind,
        "monthly": kind == MONTHLY,
        "this_period": spec["this_period"],
        "subject": subject,
        "issue_number": number,
        # The welcome note and the "coming next week" block belong to the first
        # weekly newsletter only; later issues leave them out.
        "first_issue": first_issue,
        "since": since,
        "papers_all_time": all_time,
        "max_listed": MAX_LISTED,
        # Everything that qualifies, for the admin page to show what is cut off.
        "all_events": events,
        "all_special_issues": special_issues,
        "all_jobs": jobs,
        "issue_date": now,
        "events": events[:MAX_LISTED],
        "special_issues": special_issues[:MAX_LISTED],
        "jobs": jobs[:MAX_LISTED],
        "papers": papers,
        "papers_heading": papers_heading,
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


def has_content(context):
    """True when at least one listing section would appear in the issue."""
    return any(context[key] for key in ("events", "special_issues", "jobs", "papers"))


def create_newsletter_campaign(kind=WEEKLY, now=None, only_if_content=False):
    """Render this issue and store the snapshot CM will fetch. Not sent yet.

    With ``only_if_content`` an issue with nothing to list returns ``None`` instead
    (the Friday cron uses this, so a quiet period sends nothing)."""
    now = now or timezone.now()
    context = newsletter_context(kind, now)
    if only_if_content and not has_content(context):
        return None
    html, text = render_newsletter(context)
    return EmailCampaign.objects.create(
        kind=KINDS[kind]["campaign_kind"], subject=context["subject"],
        html=html, text=text, period_start=context["since"], period_end=now,
    )
