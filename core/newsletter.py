"""The Labor Hub newsletter: live listings around hand-written issue text.

``newsletter_context`` pulls what is open right now (events, special issues and
jobs, split into newly added and deadlines this week, plus the most downloaded
discussion papers added in the last two weeks) and wraps it in the
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
    "jm_intro": ("Here are all the job market papers we have received so far, a great way to "
                 "discover this year's candidates."),
    "next_title": "Job Market Papers",
    "next_body": ("We'll launch a special page listing all the job market papers we have "
                  "received, a great way to discover this year's candidates."),
    "next_note": "Students on the market can still join the Hub, with sign-off from their advisor.",
}

MAX_LISTED = 6
MAX_PAPERS = 5
DEADLINE_DAYS = 7  # "Deadlines This Week" window, for the monthly issue too
PAPER_WINDOW = timedelta(days=14)  # a paper is "new" for two weeks, in both issues

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


def job_market_papers():
    """All approved job market papers for the newsletter's box, newest first (J2, J1)."""
    return [{
        "number": p.display_number, "title": p.title,
        "url": absolute_url(reverse("publication_detail", kwargs={"pk": p.pk})),
        "download_url": absolute_url(reverse("publication_download", kwargs={"pk": p.pk})),
        "authors": ", ".join(str(a) for a in p.ordered_authors),
        "all_time": p.download_count,
    } for p in Publication.job_market_listing()]


def paper_downloads(kind=WEEKLY, now=None):
    """Downloads in this issue's period for *every* approved discussion paper, not just
    the top few: ``{"since", "until", "rows"}`` with ``rows`` most downloaded first."""
    now = now or timezone.now()
    since = period_start(kind, now)
    rows = [{
        "number": p.display_number or "", "title": p.title,
        "url": absolute_url(reverse("publication_detail", kwargs={"pk": p.pk})),
        "authors": ", ".join(str(a) for a in p.ordered_authors),
        "period": p.period_downloads, "all_time": p.download_count,
    } for p in Publication.downloads_since(since)]
    return {"since": since, "until": now, "rows": rows}


def newsletter_context(kind=WEEKLY, now=None):
    now = now or timezone.now()
    today = timezone.localdate(now)
    number = issue_number(kind)
    spec = KINDS[kind]
    first_issue = kind == WEEKLY and number == 1
    url = lambda name, **kw: absolute_url(reverse(name, kwargs=kw))  # noqa: E731

    since = period_start(kind, now)
    window_end = today + timedelta(days=DEADLINE_DAYS)

    def split(objs, day_of, item):
        """Newly added since the last issue (newest first) and, of the rest, those whose
        deadline falls in the next DEADLINE_DAYS (soonest first). A new item that is also
        due soon stays in "new" only."""
        new, due = [], []
        for obj in objs:
            day = day_of(obj)
            added = obj.reviewed_at or obj.created_at
            if added >= since:
                new.append((added, item(obj, day)))
            elif day is not None and today <= day < window_end:
                due.append(item(obj, day))
        return [row for _, row in sorted(new, key=lambda t: t[0], reverse=True)], due

    def event_item(event, day):
        place = f" \u00b7 {event.location}" if event.location else ""
        return {
            "title": event.title, "url": url("event-detail", pk=event.pk),
            "meta": f"{event.get_category_display()}{place} \u00b7 {event.date:%B} {event.date.day}, {event.date.year}",
            "deadline": _deadline_label(day, today) if day and day >= today else "",
        }

    new_events, due_events = split(
        Event.objects.filter(Q(date__gte=now) | Q(deadline__gte=now - timedelta(days=1)),
                             status="approved").order_by("deadline"),
        lambda e: timezone.localtime(e.deadline).date() if e.deadline else None, event_item)

    new_special_issues, due_special_issues = split(
        SpecialIssue.objects.filter(status="approved", submission_deadline__gte=today)
        .order_by("submission_deadline"),
        lambda si: si.submission_deadline,
        lambda si, day: {
            "title": si.title, "url": url("special-issue-detail", pk=si.pk), "meta": si.journal,
            "deadline": _deadline_label(day, today)})

    new_jobs, due_jobs = split(
        Job.objects.filter(status="approved", deadline__gte=today).order_by("deadline"),
        lambda j: j.deadline,
        lambda job, day: {
            "title": job.title, "url": url("job-detail", pk=job.pk),
            "meta": " \u00b7 ".join(x for x in [job.employer, ", ".join(job.country_labels())] if x),
            "deadline": _deadline_label(day, today)})

    # Only papers added in the last two weeks, most downloaded in that time first
    # (a paper nobody has downloaded yet still counts). No new papers, no section.
    papers_since = now - PAPER_WINDOW
    papers = [{
        "rank": i, "title": p.title, "url": url("publication_detail", pk=p.pk),
        "download_url": url("publication_download", pk=p.pk),
        "authors": ", ".join(str(a) for a in p.ordered_authors),
        # Not shown in the email; the admin's preview lists them.
        "downloads": p.period_downloads,
        "all_time": p.download_count,
    } for i, p in enumerate(Publication.new_since(papers_since)[:MAX_PAPERS], start=1)]

    jm_papers = job_market_papers()
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
        "job_market_papers": jm_papers,
        "subject": subject,
        "issue_number": number,
        # The welcome note and the "coming next week" block belong to the first
        # weekly newsletter only; later issues leave them out.
        "first_issue": first_issue,
        "since": since,
        "papers_since": papers_since,
        "max_listed": MAX_LISTED,
        # Everything that qualifies, for the admin page to show what is cut off.
        "all_new_events": new_events, "all_due_events": due_events,
        "all_new_special_issues": new_special_issues, "all_due_special_issues": due_special_issues,
        "all_new_jobs": new_jobs, "all_due_jobs": due_jobs,
        "issue_date": now,
        "new_events": new_events[:MAX_LISTED], "due_events": due_events[:MAX_LISTED],
        "new_special_issues": new_special_issues[:MAX_LISTED],
        "due_special_issues": due_special_issues[:MAX_LISTED],
        "new_jobs": new_jobs[:MAX_LISTED], "due_jobs": due_jobs[:MAX_LISTED],
        "papers": papers,
        "papers_heading": "Most downloaded new papers",
        "site_url": settings.SITE_URL.rstrip("/"),
        "logo_src": absolute_url(static("images/logo.png")),
        "urls": {
            "login": url("login"), "announcements": url("announcements"),
            "events": url("events-list"), "special_issues": url("special-issues-list"),
            "jobs": url("jobs-list"), "visits": url("seminars-list"),
            "papers": absolute_url(reverse("publications")) + "?type=discussion",
            "job_market": absolute_url(reverse("publications")) + "?type=job_market",
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
    return any(context[key] for key in (
        "new_events", "due_events", "new_special_issues", "due_special_issues",
        "new_jobs", "due_jobs", "papers"))


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
