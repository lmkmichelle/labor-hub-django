from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_GET
from django.views.generic import ListView

from accounts.models import CustomUser
from core.constants import COUNTRY_CHOICES
from core.filters import map_country_terms_to_codes, parse_pill_terms
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
            "subtitle": user.profile.position or "Position not specified",
            "description": user.profile.education or "",
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
            "subtitle": ", ".join(name for name in author_names if name) or "Unknown Author",
        })

    country_query = urlencode({"countries": code})

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

        query = self.request.GET.get('q', '').strip()
        if query:
            qs = qs.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(email__icontains=query) |
                Q(profile__position__icontains=query) |
                Q(profile__education__icontains=query) |
                Q(profile__research_interests__icontains=query)
            )

        selected_countries = map_country_terms_to_codes(
            parse_pill_terms(self.request.GET.get('countries', '')))
        if selected_countries:
            qs = qs.filter(profile__country_code__in=selected_countries)

        interest_terms = parse_pill_terms(self.request.GET.get('interests', ''))
        if interest_terms:
            interests_query = Q()
            for term in interest_terms:
                interests_query |= Q(profile__research_interests__icontains=term)
            qs = qs.filter(interests_query)

        sort = self.request.GET.get('sort', '')
        if sort == 'newest':
            qs = qs.order_by('-date_joined', 'id')
        else:
            qs = qs.order_by('first_name', 'last_name', 'id')

        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_countries = map_country_terms_to_codes(
            parse_pill_terms(self.request.GET.get('countries', '')))
        interest_terms = parse_pill_terms(self.request.GET.get('interests', ''))

        context['query'] = self.request.GET.get('q', '')
        context['sort'] = self.request.GET.get('sort', '')
        context['selected_countries'] = selected_countries
        context['selected_countries_serialized'] = ','.join(selected_countries)
        context['country_choices'] = COUNTRY_CHOICES
        context['selected_interests'] = interest_terms
        context['selected_interests_serialized'] = ','.join(interest_terms)

        filter_params = {}
        if context['query']:
            filter_params['q'] = context['query']
        if context['selected_countries_serialized']:
            filter_params['countries'] = context['selected_countries_serialized']
        if context['selected_interests_serialized']:
            filter_params['interests'] = context['selected_interests_serialized']
        if context['sort']:
            filter_params['sort'] = context['sort']
        context['filter_querystring'] = urlencode(filter_params)
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

    query = request.GET.get('q', '').strip()
    if query:
        publications = publications.filter(
            Q(title__icontains=query) |
            Q(abstract__icontains=query) |
            Q(topic__icontains=query) |
            Q(authors__name__icontains=query) |
            Q(authors__user__first_name__icontains=query) |
            Q(authors__user__last_name__icontains=query)
        ).distinct()

    selected_countries = map_country_terms_to_codes(
        parse_pill_terms(request.GET.get('countries', '')))
    if selected_countries:
        publications = publications.filter(country_code__in=selected_countries)

    keyword_terms = parse_pill_terms(request.GET.get('keywords', ''))
    if keyword_terms:
        keywords_query = Q()
        for term in keyword_terms:
            keywords_query |= Q(keywords__icontains=term)
        publications = publications.filter(keywords_query)

    job_market = request.GET.get('job_market') == '1'
    if job_market:
        publications = publications.filter(is_job_market=True)

    sort = request.GET.get('sort', 'newest')
    if sort == 'oldest':
        publications = publications.order_by('applied_at', 'id')
    elif sort == 'title':
        publications = publications.order_by(Lower('title'), 'id')
    else:
        sort = 'newest'
        publications = publications.order_by('-applied_at', '-id')

    paginator = Paginator(publications, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    selected_countries_serialized = ','.join(selected_countries)
    selected_keywords_serialized = ','.join(keyword_terms)

    filter_params = {}
    if query:
        filter_params['q'] = query
    if selected_countries_serialized:
        filter_params['countries'] = selected_countries_serialized
    if selected_keywords_serialized:
        filter_params['keywords'] = selected_keywords_serialized
    if job_market:
        filter_params['job_market'] = '1'
    if sort:
        filter_params['sort'] = sort

    return render(request, 'publications/publications.html', {
        'publications': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'query': query,
        'sort': sort,
        'selected_countries': selected_countries,
        'selected_countries_serialized': selected_countries_serialized,
        'country_choices': COUNTRY_CHOICES,
        'selected_keywords': keyword_terms,
        'selected_keywords_serialized': selected_keywords_serialized,
        'job_market': job_market,
        'filter_querystring': urlencode(filter_params),
    })
