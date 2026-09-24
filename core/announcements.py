"""The combined Announcements feed: jobs, events, special issues and visits.

Each type keeps its own model, list page and moderation; this module only
merges their *approved, still-relevant* rows into one newest-first stream.

The merge happens in the database as a UNION of ``(id, created_at, kind)``
rows so pagination is correct across models; only the current page's rows are
then loaded in full, one query per kind (``in_bulk``), so the cost is constant
(at most four queries plus the count) however long the feed grows.
"""
from django.db.models import CharField, Q, Value
from django.utils import timezone

from events.models import Event
from jobs.models import Job
from seminars.models import Seminar
from special_issues.models import SpecialIssue

JOB, EVENT, SPECIAL_ISSUE, VISIT = 'job', 'event', 'special_issue', 'visit'

KIND_LABELS = {
    JOB: 'Job',
    EVENT: 'Event',
    SPECIAL_ISSUE: 'Special Issue',
    VISIT: 'Visit',
}


def _open_querysets():
    """Approved rows of each type that haven't already passed."""
    now = timezone.now()
    today = timezone.localdate()
    return {
        JOB: Job.objects.approved().filter(deadline__gte=today),
        EVENT: Event.objects.approved().filter(Q(date__gte=now) | Q(end_date__gte=now)),
        SPECIAL_ISSUE: SpecialIssue.objects.approved().filter(submission_deadline__gte=today),
        VISIT: Seminar.objects.approved().filter(
            Q(visit_end__gte=today) | Q(visit_end__isnull=True, visit_start__gte=today)
        ),
    }


def announcements_queryset():
    """A UNION queryset of ``id``/``created_at``/``kind`` rows, newest first."""
    rows = [
        # order_by() clears each model's Meta.ordering, which a UNION rejects.
        queryset.order_by().values('id', 'created_at').annotate(
            kind=Value(kind, output_field=CharField())
        )
        for kind, queryset in _open_querysets().items()
    ]
    return rows[0].union(*rows[1:]).order_by('-created_at', '-id')


_LOADERS = {
    JOB: lambda ids: Job.objects.select_related('uploader').in_bulk(ids),
    EVENT: lambda ids: Event.objects.select_related('host').in_bulk(ids),
    SPECIAL_ISSUE: lambda ids: SpecialIssue.objects.select_related('posted_by').in_bulk(ids),
    VISIT: lambda ids: Seminar.objects.select_related('posted_by', 'university').in_bulk(ids),
}


def load_announcements(rows):
    """Turn union rows into ``[{'kind', 'label', 'obj'}]``, keeping their order."""
    rows = list(rows)
    ids_by_kind = {}
    for row in rows:
        ids_by_kind.setdefault(row['kind'], []).append(row['id'])
    objects = {kind: _LOADERS[kind](ids) for kind, ids in ids_by_kind.items()}
    return [
        {'kind': row['kind'], 'label': KIND_LABELS[row['kind']], 'obj': objects[row['kind']][row['id']]}
        for row in rows
    ]


def _summary(entry):
    """Map one loaded announcement onto the keys partials/_list_item.html reads."""
    obj, kind = entry['obj'], entry['kind']
    if kind == JOB:
        title = obj.title
        subtitle = obj.employer or 'Employer not specified'
        description = ', '.join(obj.country_labels())
    elif kind == EVENT:
        title = obj.title
        subtitle = obj.location
        description = ''
    elif kind == SPECIAL_ISSUE:
        title = obj.title
        subtitle = obj.journal
        description = f"Deadline {obj.submission_deadline.strftime('%b %d, %Y')}"
    else:
        title = obj.visitor_name or 'Visiting scholar'
        subtitle = f'Visiting {obj.get_university_display()}'
        description = ', '.join(obj.country_labels())
    return {
        'url': obj.get_absolute_url(),
        'title': title,
        'date': timezone.localtime(obj.created_at).strftime('%b %d'),
        'subtitle': subtitle,
        'description': description,
        'badge': {'text': entry['label']},
        'is_example': obj.is_example,
    }


def recent_announcement_summaries(limit=6):
    """The newest ``limit`` announcements as dicts for partials/_list_display.html."""
    return [_summary(e) for e in load_announcements(announcements_queryset()[:limit])]
