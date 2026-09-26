from django.conf import settings
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.http import Http404, HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import DeleteView, ListView, TemplateView

from accounts.models import CustomUser
from core.models import City
from core.constants import (
    COUNTRY_CHOICES,
    PAPER_COUNTRY_CHOICES,
    PAPER_SPECIAL_COUNTRY_CODES,
)
from core.announcements import (
    announcements_queryset,
    load_announcements,
    recent_announcement_summaries,
)
from core.filters import map_country_terms_to_codes, parse_pill_terms
from core.forms import ContactForm
from publications.models import Publication
from events.models import Event
from jobs.models import Job
from seminars.models import Seminar

country_name_to_code = {name.lower(): code for code, name in COUNTRY_CHOICES}


class OwnerDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a content row, but only one the current user owns.

    Subclasses set ``model``, ``owner_field`` (``host`` / ``uploader`` /
    ``posted_by``) and ``success_url``. Restricting the queryset to the owner
    means a non-owner gets a plain 404 and learns nothing about the row. The
    GET renders templates/partials/_confirm_delete.html; the POST deletes.
    """
    owner_field = None
    template_name = "partials/_confirm_delete.html"
    success_message = "Deleted."

    def get_queryset(self):
        return super().get_queryset().filter(
            **{self.owner_field: self.request.user}
        )

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("cancel_url", self.get_success_url())
        return context


@require_GET
def healthz(request):
    """Liveness/readiness probe: 200 when the DB answers, 503 otherwise.

    Unauthenticated and dependency-light so uptime monitors and the Upsun router
    can check the app is up without touching business logic.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return HttpResponse("db error", status=503, content_type="text/plain")
    return HttpResponse("ok", status=200, content_type="text/plain")


class SuperuserTemplateView(UserPassesTestMixin, TemplateView):
    """A static page restricted to superusers.

    Used for the internal admin guides. ``raise_exception`` is deliberately left
    at its default of False: AccessMixin then sends an anonymous visitor to the
    login page (where signing in may well grant access) but raises
    PermissionDenied -> templates/403.html for someone already signed in, whom a
    login form would only confuse. Setting it True would 403 both.
    """

    def test_func(self):
        return self.request.user.is_superuser


def home(request):
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
            # Unnumbered (unapproved or example) papers aren't actually part
            # of the discussion series yet. display_number covers both the
            # regular series ("5") and a job-market paper's own "J" series.
            'subtitle': (
                f'Discussion Paper No. {paper.display_number}'
                if paper.display_number else ''
            ),
            'is_example': paper.is_example,
            'description': ', '.join(authors) if authors else 'Unknown Author'
        })

    context = {
        'new_scholars': new_scholars,
        'recent_papers': recent_papers,
        'recent_announcements': recent_announcement_summaries(),
    }

    return render(request, 'core/home.html', context)


def announcements(request):
    """Every recent job, event, special issue and visit in one newest-first feed."""
    page_obj = Paginator(announcements_queryset(), 10).get_page(request.GET.get('page'))
    return render(request, 'core/announcements.html', {
        'page_obj': page_obj,
        'is_paginated': page_obj.paginator.num_pages > 1,
        'announcements': load_announcements(page_obj.object_list),
    })


@login_required
def post_announcement(request):
    """Pick a category first; each category's own form then asks only its fields."""
    return render(request, 'core/post_announcement.html', {
        'can_post_special_issue': request.user.is_researcher(),
    })


def map_view(request):
    return render(request, 'core/map.html')


def _send_contact_notification(contact_message):
    """Email the site's contact mailbox about a new submission.

    Sent from ``DEFAULT_FROM_EMAIL`` (a domain the relay is allowed to send as)
    with ``Reply-To`` set to the submitter, so admins can reply directly. Fails
    silently because the message is already persisted; a mail hiccup must not
    500 the visitor.
    """
    recipients = [
        addr.strip()
        for addr in settings.CONTACT_EMAIL.split(',')
        if addr.strip()
    ]
    if not recipients:
        return
    body = (
        f"Name: {contact_message.name}\n"
        f"Email: {contact_message.email}\n"
        f"Submitted: {contact_message.created_at:%Y-%m-%d %H:%M}\n\n"
        f"{contact_message.message}\n"
    )
    EmailMessage(
        subject=f"[Labor Hub] Contact form: {contact_message.name}",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
        reply_to=[contact_message.email],
    ).send(fail_silently=True)


@require_http_methods(["GET", "POST"])
def contact(request):
    """Public contact form: store the message, notify admins, confirm to user."""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            if not form.is_spam():
                message = form.save()
                _send_contact_notification(message)
            # Redirect either way (PRG) so refreshes don't resubmit and bots
            # that trip the honeypot get an indistinguishable success page.
            return redirect(f"{reverse('contact')}?sent=1")
    else:
        form = ContactForm()

    return render(request, 'core/contact.html', {
        'form': form,
        'sent': request.GET.get('sent') == '1',
    })


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
        .exclude(country_code__in=PAPER_SPECIAL_COUNTRY_CODES)
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
    if code in PAPER_SPECIAL_COUNTRY_CODES:
        raise Http404("No map panel for that code.")
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
            "description": user.profile.department or "",
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
        "scholars_see_all_url": f"{reverse('scholars')}?{country_query}",
        "papers": papers,
        "papers_total": papers_total,
        "papers_more": papers_total > MAP_PANEL_LIMIT,
        "papers_see_all_url": f"{reverse('publications')}?{country_query}",
    }
    return render(request, "partials/_map_panel.html", context)

class ScholarsListView(ListView):
    """Unified directory of every member (students and researchers).

    Consolidates the former separate researcher/student pages into a single page
    that shares the search box + sidebar filter layout used elsewhere on the
    site. Administrators are excluded so the directory only lists the two
    membership categories. The optional ``role`` filter narrows the list to
    students and/or researchers.
    """

    model = CustomUser
    template_name = 'accounts/users_list.html'
    context_object_name = 'users'
    paginate_by = 12

    MEMBER_ROLES = (CustomUser.Role.STUDENT, CustomUser.Role.RESEARCHER)

    def _selected_roles(self):
        valid = {CustomUser.Role.STUDENT.value, CustomUser.Role.RESEARCHER.value}
        return [role for role in self.request.GET.getlist('role') if role in valid]

    def get_queryset(self):
        qs = CustomUser.objects.filter(
            is_active=True, role__in=self.MEMBER_ROLES
        ).select_related('profile')

        query = self.request.GET.get('q', '').strip()
        if query:
            qs = qs.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(email__icontains=query) |
                Q(profile__position__icontains=query) |
                Q(profile__department__icontains=query) |
                Q(profile__university__name__icontains=query) |
                Q(profile__university_name__icontains=query) |
                Q(profile__research_interests__icontains=query)
            )

        selected_roles = self._selected_roles()
        if selected_roles:
            qs = qs.filter(role__in=selected_roles)

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
            qs = qs.order_by('last_name', 'first_name', 'id')

        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_countries = map_country_terms_to_codes(
            parse_pill_terms(self.request.GET.get('countries', '')))
        interest_terms = parse_pill_terms(self.request.GET.get('interests', ''))
        selected_roles = self._selected_roles()

        context['query'] = self.request.GET.get('q', '')
        context['sort'] = self.request.GET.get('sort', '')
        context['selected_countries'] = selected_countries
        context['selected_countries_serialized'] = ','.join(selected_countries)
        context['country_choices'] = COUNTRY_CHOICES
        context['selected_interests'] = interest_terms
        context['selected_interests_serialized'] = ','.join(interest_terms)
        context['role_choices'] = [
            (CustomUser.Role.STUDENT.value, 'Students'),
            (CustomUser.Role.RESEARCHER.value, 'Researchers'),
        ]
        context['selected_roles'] = selected_roles

        filter_pairs = []
        if context['query']:
            filter_pairs.append(('q', context['query']))
        if context['selected_countries_serialized']:
            filter_pairs.append(('countries', context['selected_countries_serialized']))
        if context['selected_interests_serialized']:
            filter_pairs.append(('interests', context['selected_interests_serialized']))
        for role in selected_roles:
            filter_pairs.append(('role', role))
        if context['sort']:
            filter_pairs.append(('sort', context['sort']))
        context['filter_querystring'] = urlencode(filter_pairs)
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
@cache_control(max_age=86400)
def cities_by_country(request):
    """City suggestions for the event-location picker.

    Unlike ``search_accounts`` in seminars/views.py's university endpoint,
    there is no live fallback fetch here: the City table is a one-time
    GeoNames import (see ``import_cities``), not something to hit a
    third-party API for on every miss.
    """
    country_code = (request.GET.get('country') or '').strip().upper()
    valid_codes = {code for code, _ in COUNTRY_CHOICES}
    if country_code not in valid_codes:
        return JsonResponse({'cities': []})

    queryset = City.objects.filter(country_code=country_code)
    return JsonResponse({'cities': [city.display_name for city in queryset]})


COUNTRY_NAME_BY_CODE = dict(COUNTRY_CHOICES)
CITY_SEARCH_LIMIT = 12


@require_GET
@cache_control(max_age=3600)
def city_search(request):
    """City-first typeahead for the location picker (static/js/location-picker.js).

    Backed entirely by the local GeoNames import (core.models.City) -- no
    third-party geocoding API, no key, no per-request cost. Ranks a prefix
    match by population first (the way a user expects "new y" to surface
    "New York" over a same-prefix small town), then tops up with infix
    matches so "york" still finds "New York".
    """
    query = (request.GET.get('q') or '').strip()
    if len(query) < 2:
        return JsonResponse({'cities': []})

    prefix_matches = list(
        City.objects.filter(name__istartswith=query).order_by('-population')[:CITY_SEARCH_LIMIT]
    )
    remaining = CITY_SEARCH_LIMIT - len(prefix_matches)
    infix_matches = []
    if remaining > 0:
        exclude_ids = [c.id for c in prefix_matches]
        infix_matches = list(
            City.objects.filter(name__icontains=query)
            .exclude(id__in=exclude_ids)
            .order_by('-population')[:remaining]
        )

    results = []
    for city in prefix_matches + infix_matches:
        country_name = COUNTRY_NAME_BY_CODE.get(city.country_code, city.country_code)
        label = ", ".join(
            part for part in (city.name, city.admin1_name, country_name) if part
        )
        results.append({
            'name': city.name,
            'admin1_name': city.admin1_name,
            'admin1_code': city.admin1_code,
            'country_code': city.country_code,
            'country_name': country_name,
            'latitude': city.latitude,
            'longitude': city.longitude,
            'label': label,
        })

    return JsonResponse({'cities': results})


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
        parse_pill_terms(request.GET.get('countries', '')),
        choices=PAPER_COUNTRY_CHOICES)
    if selected_countries:
        publications = publications.filter(country_code__in=selected_countries)

    topic_terms = parse_pill_terms(request.GET.get('topics', ''))
    if topic_terms:
        topics_query = Q()
        for term in topic_terms:
            # topic is a JSONField list; __icontains works on SQLite/MySQL
            # (the app's engines) but not on Postgres jsonb.
            topics_query |= Q(topic__icontains=term)
        publications = publications.filter(topics_query)

    paper_type = request.GET.get('type', '')
    if request.GET.get('job_market') == '1':
        paper_type = 'job_market'
    if paper_type == 'discussion':
        publications = publications.filter(is_job_market=False)
    elif paper_type == 'job_market':
        publications = publications.filter(is_job_market=True)
    else:
        paper_type = ''
    page_heading = {
        'discussion': 'Discussion Papers',
        'job_market': 'Job Market Papers',
    }.get(paper_type, 'Research Papers')

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
    selected_topics_serialized = ','.join(topic_terms)

    filter_params = {}
    if query:
        filter_params['q'] = query
    if selected_countries_serialized:
        filter_params['countries'] = selected_countries_serialized
    if selected_topics_serialized:
        filter_params['topics'] = selected_topics_serialized
    if paper_type:
        filter_params['type'] = paper_type
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
        'country_choices': PAPER_COUNTRY_CHOICES,
        'selected_topics': topic_terms,
        'selected_topics_serialized': selected_topics_serialized,
        'paper_type': paper_type,
        'page_heading': page_heading,
        'filter_querystring': urlencode(filter_params),
    })
