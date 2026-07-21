import json
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_GET
from django.views.generic import ListView

from accounts.models import CustomUser
from core.constants import COUNTRY_CHOICES
from publications.models import Publication
from events.models import Event
from seminars.models import Seminar

country_name_to_code = {name.lower(): code for code, name in COUNTRY_CHOICES}

def home(request):
    # Get upcoming events (next 6)
    upcoming_events_qs = Event.objects.filter(
        status='approved',
        date__gte=timezone.now()
    ).order_by('date')[:6]

    # Format events for _list_display template
    upcoming_events = []
    for event in upcoming_events_qs:
        upcoming_events.append({
            'url': f'/events/{event.id}/',
            'title': event.title,
            'date': event.date.strftime('%b %d'),
            'subtitle': f'Discussion Series #{event.id}' if hasattr(event, 'id') else '',
            'description': f'📍 {event.location}',
            'badge': {
                'class': 'bg-primary',
                'text': event.get_category_display()
            },
            'meta': {
                'right': event.date.strftime('%H:%M')
            }
        })

    # Get upcoming seminars (next 6)
    today = timezone.localdate()
    upcoming_seminars_qs = Seminar.objects.filter(
        Q(visit_end__gte=today) |
        Q(visit_end__isnull=True, visit_start__gte=today)
    ).order_by('visit_start')[:6]

    # Format seminars for _list_display template
    upcoming_seminars = []
    for seminar in upcoming_seminars_qs:
        country_labels = seminar.country_labels()
        if seminar.visit_start and seminar.visit_end and seminar.visit_end != seminar.visit_start:
            seminar_date = f"{seminar.visit_start.strftime('%b %d')} - {seminar.visit_end.strftime('%b %d')}"
        elif seminar.visit_start:
            seminar_date = seminar.visit_start.strftime('%b %d')
        elif seminar.visit_end:
            seminar_date = seminar.visit_end.strftime('%b %d')
        else:
            seminar_date = ''
        upcoming_seminars.append({
            'url': f'/seminars/{seminar.id}/',
            'title': seminar.visitor_name or 'Visiting scholar',
            'date': seminar_date,
            'subtitle': f'Visiting {seminar.get_university_display()}',
            'description': seminar.visitor_affiliation or '',
            'meta': {'right': ', '.join(country_labels[:2]) if country_labels else ''}
        })

    # Get new scholars (recently joined, last 6)
    new_scholars_qs = CustomUser.objects.filter(
        is_active=True,
        profile__isnull=False
    ).order_by('-date_joined')[:6]

    # Format scholars for _list_display template
    new_scholars = []
    for scholar in new_scholars_qs:
        new_scholars.append({
            'url': f'/profile/{scholar.pk}/',
            'title': scholar.get_full_name(),
            'date': scholar.date_joined.strftime('%b %d'),
            'subtitle': scholar.profile.position or 'Position not specified',
            'description': scholar.profile.get_country_code_display() if scholar.profile.country_code else ''
        })

    # Get recent approved papers (last 6)
    recent_papers_qs = Publication.objects.filter(
        status='approved'
    ).prefetch_related('authors__user').order_by('-applied_at')[:6]

    # Format papers for _list_display template
    recent_papers = []
    for paper in recent_papers_qs:
        authors = []
        for author in paper.authors.all():
            if author.user:
                authors.append(author.user.get_full_name())
            else:
                authors.append(author.name)

        recent_papers.append({
            'url': f'/publications/{paper.id}/',
            'title': paper.title,
            'date': paper.applied_at.strftime('%b %d'),
            'subtitle': f'Discussion Series #{paper.id}',
            'description': ', '.join(authors) if authors else 'Unknown Author'
        })

    context = {
        'upcoming_events': upcoming_events,
        'upcoming_seminars': upcoming_seminars,
        'new_scholars': new_scholars,
        'recent_papers': recent_papers,
    }

    return render(request, 'core/home.html', context)


def map_view(request):
    return render(request, 'core/map.html')


MAP_PANEL_LIMIT = 5


@require_GET
def map_summary(request):
    """Per-country counts used only to color the world map.

    Returns a compact ``{CODE: {"scholars": n, "papers": n}}`` mapping built with
    database aggregation instead of shipping every scholar/paper row, so the
    payload stays small as the dataset grows. Country codes are upper-cased so
    they line up with the SVG path ids.
    """
    summary = {}

    scholar_counts = (
        CustomUser.objects.filter(is_active=True, profile__country_code__isnull=False)
        .exclude(profile__country_code="")
        .values("profile__country_code")
        .annotate(total=Count("id"))
    )
    for row in scholar_counts:
        code = row["profile__country_code"].upper()
        summary.setdefault(code, {"scholars": 0, "papers": 0})["scholars"] += row["total"]

    paper_counts = (
        Publication.objects.filter(status="approved", country_code__isnull=False)
        .exclude(country_code="")
        .values("country_code")
        .annotate(total=Count("id"))
    )
    for row in paper_counts:
        code = row["country_code"].upper()
        summary.setdefault(code, {"scholars": 0, "papers": 0})["papers"] += row["total"]

    return JsonResponse(summary)


@require_GET
def map_country_detail(request, code):
    """Server-rendered side-panel fragment for a single country.

    Returns the top ``MAP_PANEL_LIMIT`` scholars (alphabetical) and papers (most
    recent) for ``code`` plus totals and "see all" links. Rendering the cards
    server-side keeps their markup identical to the rest of the site (reuses the
    shared ``_list_item`` partial) and avoids duplicating card HTML in JavaScript.
    """
    code = code.upper()
    country_name = dict(COUNTRY_CHOICES).get(code, code)

    scholars_qs = (
        CustomUser.objects.select_related("profile")
        .filter(is_active=True, profile__country_code__iexact=code)
        .order_by("first_name", "last_name")
    )
    scholars_total = scholars_qs.count()
    scholars = [
        {
            "title": user.get_full_name() or user.email,
            "url": f"/profile/{user.pk}/",
            "badge": user.profile.position or "",
            "subtitle": user.profile.education or "",
        }
        for user in scholars_qs[:MAP_PANEL_LIMIT]
    ]

    papers_qs = (
        Publication.objects.filter(status="approved", country_code__iexact=code)
        .prefetch_related("authors__user")
        .order_by("-applied_at")
    )
    papers_total = papers_qs.count()
    papers = []
    for paper in papers_qs[:MAP_PANEL_LIMIT]:
        author_names = [
            author.user.get_full_name() if author.user else author.name
            for author in paper.authors.all()
        ]
        papers.append({
            "title": paper.title,
            "url": f"/publications/{paper.id}/",
            "badge": f"Discussion Series #{paper.id}",
            "subtitle": ", ".join(name for name in author_names if name) or "Unknown Author",
        })

    country_query = urlencode({"q": country_name, "filter": "country"})

    context = {
        "country_code": code,
        "country_name": country_name,
        "scholars": scholars,
        "scholars_total": scholars_total,
        "scholars_more": scholars_total > MAP_PANEL_LIMIT,
        "scholars_see_all_url": f"{reverse('researchers')}?{country_query}",
        "papers": papers,
        "papers_total": papers_total,
        "papers_more": papers_total > MAP_PANEL_LIMIT,
        "papers_see_all_url": f"{reverse('publications')}?{country_query}",
    }
    return render(request, "partials/_map_panel.html", context)

class UserListView(ListView):
    model = CustomUser
    template_name = 'accounts/users_list.html'
    context_object_name = 'users'
    paginate_by = 10

    role = None

    def get_queryset(self):
        qs = CustomUser.objects.filter(is_active=True, role=self.role).select_related('profile')

        query = self.request.GET.get('q', '')
        filter_type = self.request.GET.get('filter', 'all')

        if query:
            if filter_type == 'name':
                qs = qs.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query))
            elif filter_type == 'email':
                qs = qs.filter(email__icontains=query)
            elif filter_type == 'country':
                matching_codes = [
                    code for code, name in COUNTRY_CHOICES
                    if query.strip().lower() in name.lower()
                ]
                if matching_codes:
                    qs = qs.filter(profile__country_code__in=matching_codes)
                else:
                    qs = qs.filter(profile__country_code__iexact=query)
            elif filter_type == 'position':
                qs = qs.filter(profile__position__icontains=query)
            elif filter_type == 'research_interests':
                qs = qs.filter(profile__research_interests__icontains=query)
            else:
                qs = qs.filter(
                    Q(first_name__icontains=query) |
                    Q(last_name__icontains=query) |
                    Q(email__icontains=query) |
                    Q(profile__position__icontains=query) |
                    Q(profile__country_code__icontains=query) |
                    Q(profile__research_interests__icontains=query))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['COUNTRY_CHOICES'] = COUNTRY_CHOICES
        context['query'] = self.request.GET.get('q', '')
        context['filter_type'] = self.request.GET.get('filter', 'all')
        context['countries'] = dict(COUNTRY_CHOICES)
        context['user_filters'] = [
            {'value': 'all', 'label': 'All Fields'},
            {'value': 'name', 'label': 'Name'},
            {'value': 'country', 'label': 'Country'},
            {'value': 'position', 'label': 'Position'},
            {'value': 'research_interests', 'label': 'Research Interests'},
        ]
        return context

class ResearchersListView(UserListView):
    role = CustomUser.Role.RESEARCHER

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_type'] = 'researcher'
        return context

class StudentsListView(UserListView):
    role = CustomUser.Role.STUDENT

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_type'] = 'student'
        return context

@require_GET
def search_accounts(request):
    query = request.GET.get('q', '')
    users = CustomUser.objects.filter(first_name__icontains=query)[:10]
    return JsonResponse([
        {'value': f"{u.first_name} {u.last_name}", 'id': str(u.id)}
        for u in users
    ], safe=False)

@require_GET
def publications_list(request):
    publications = Publication.objects.filter(status='approved').prefetch_related('authors__user')

    query = request.GET.get('q', '')

    def parse_query_terms(raw_query):
        raw_query = (raw_query or '').strip()
        if not raw_query:
            return []

        parsed_terms = []
        if raw_query.startswith('['):
            try:
                parsed = json.loads(raw_query)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict):
                            value = str(item.get('value', '')).strip()
                        else:
                            value = str(item).strip()
                        if value:
                            parsed_terms.append(value)
            except (TypeError, ValueError, json.JSONDecodeError):
                parsed_terms = []

        if not parsed_terms:
            parsed_terms = [part.strip() for part in raw_query.split(',') if part.strip()]

        deduped_terms = []
        seen = set()
        for term in parsed_terms:
            lowered = term.lower()
            if lowered not in seen:
                seen.add(lowered)
                deduped_terms.append(term)
        return deduped_terms

    query_terms = parse_query_terms(query)
    filter_type = request.GET.get('filter', 'all')

    publication_filters = [
        {'value': 'all', 'label': 'All'},
        {'value': 'title', 'label': 'Title'},
        {'value': 'authors', 'label': 'Authors'},
        {'value': 'country', 'label': 'Country'},
        {'value': 'keywords', 'label': 'Keywords'},
    ]

    if query_terms:
        if filter_type == 'title':
            title_query = Q()
            for term in query_terms:
                title_query |= Q(title__icontains=term)
            publications = publications.filter(title_query)
        elif filter_type == 'authors':
            authors_query = Q()
            for term in query_terms:
                authors_query |= (
                    Q(authors__name__icontains=term) |
                    Q(authors__user__first_name__icontains=term) |
                    Q(authors__user__last_name__icontains=term)
                )
            publications = publications.filter(authors_query).distinct()
        elif filter_type == 'country':
            matching_codes = set()
            available_codes = {code for code, _ in COUNTRY_CHOICES}
            for term in query_terms:
                normalized = term.strip().lower()
                upper_term = term.strip().upper()
                if upper_term in available_codes:
                    matching_codes.add(upper_term)
                for code, name in COUNTRY_CHOICES:
                    if normalized in name.lower():
                        matching_codes.add(code)
            if matching_codes:
                publications = publications.filter(country_code__in=matching_codes)
            else:
                publications = publications.none()
        elif filter_type == 'keywords':
            keywords_query = Q()
            for term in query_terms:
                keywords_query |= Q(keywords__icontains=term)
            publications = publications.filter(keywords_query)
        else:
            all_query = Q()
            for term in query_terms:
                all_query |= (
                    Q(title__icontains=term) |
                    Q(authors__name__icontains=term) |
                    Q(authors__user__first_name__icontains=term) |
                    Q(authors__user__last_name__icontains=term) |
                    Q(abstract__icontains=term) |
                    Q(country_code__icontains=term) |
                    Q(keywords__icontains=term) |
                    Q(study_url__icontains=term) |
                    Q(is_job_market__icontains=term)
                )
            publications = publications.filter(all_query).distinct()

    paginator = Paginator(publications, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    countries = dict(COUNTRY_CHOICES)

    return render(request, 'publications/publications.html', {
        'publications': page_obj,
        'COUNTRY_CHOICES': COUNTRY_CHOICES,
        'query': json.dumps([{'value': term} for term in query_terms]) if query_terms else '',
        'filter_type': filter_type,
        'countries': countries,
        'publication_filters': publication_filters,
    })
