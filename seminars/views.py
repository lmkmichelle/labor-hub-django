import json
from urllib.parse import urlencode
from urllib.request import urlopen

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, DetailView, ListView
from core.constants import COUNTRY_CHOICES

from seminars.forms import SeminarForm
from seminars.models import Seminar, University


COUNTRY_MAP = dict(COUNTRY_CHOICES)


def _parse_country_terms(raw_value):
    raw_value = (raw_value or '').strip()
    if not raw_value:
        return []

    parsed_terms = []
    if raw_value.startswith('['):
        import json

        try:
            parsed = json.loads(raw_value)
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
        parsed_terms = [part.strip() for part in raw_value.split(',') if part.strip()]

    deduped_terms = []
    seen = set()
    for term in parsed_terms:
        lowered = term.lower()
        if lowered not in seen:
            seen.add(lowered)
            deduped_terms.append(term)
    return deduped_terms


def _map_country_terms_to_codes(terms):
    if not terms:
        return []

    available_codes = {code for code, _ in COUNTRY_CHOICES}
    selected_codes = []
    seen = set()

    for term in terms:
        normalized = term.strip().lower()
        upper_term = term.strip().upper()

        if upper_term in available_codes and upper_term not in seen:
            seen.add(upper_term)
            selected_codes.append(upper_term)
            continue

        for code, label in COUNTRY_CHOICES:
            if normalized == label.lower() or normalized in label.lower():
                if code not in seen:
                    seen.add(code)
                    selected_codes.append(code)

    return selected_codes


class SeminarsListView(ListView):
    model = Seminar
    template_name = 'seminars/seminars_list.html'
    context_object_name = 'seminars'
    paginate_by = 10

    def get_queryset(self):
        queryset = Seminar.objects.select_related('posted_by', 'university')

        show_archived = self.request.GET.get('show_archived') == '1'
        today = timezone.localdate()
        if show_archived:
            queryset = queryset.filter(
                Q(visit_end__lt=today) |
                Q(visit_end__isnull=True, visit_start__lt=today)
            )
        else:
            queryset = queryset.filter(
                Q(visit_end__gte=today) |
                Q(visit_end__isnull=True, visit_start__gte=today)
            )

        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(visitor_name__icontains=query) |
                Q(visitor_email__icontains=query) |
                Q(visitor_affiliation__icontains=query) |
                Q(university__name__icontains=query) |
                Q(university_name__icontains=query)
            )

        country_terms = _parse_country_terms(self.request.GET.get('countries', ''))
        selected_countries = _map_country_terms_to_codes(country_terms)
        if selected_countries:
            matching_ids = []
            for seminar in queryset:
                countries = seminar.countries or []
                if any(code in countries for code in selected_countries):
                    matching_ids.append(seminar.id)
            queryset = queryset.filter(id__in=matching_ids)

        sort = self.request.GET.get('sort', '')
        if sort == 'newest':
            queryset = queryset.order_by('-id')
        else:
            if show_archived:
                queryset = queryset.order_by('-visit_start', '-id')
            else:
                queryset = queryset.order_by('visit_start', '-id')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        country_terms = _parse_country_terms(self.request.GET.get('countries', ''))
        selected_countries = _map_country_terms_to_codes(country_terms)

        context['query'] = self.request.GET.get('q', '')
        context['show_archived'] = self.request.GET.get('show_archived') == '1'
        context['sort'] = self.request.GET.get('sort', '')
        context['selected_countries'] = selected_countries
        context['selected_country_labels'] = [COUNTRY_MAP.get(code, code) for code in selected_countries]
        context['selected_countries_serialized'] = ','.join(selected_countries)
        context['country_choices'] = COUNTRY_CHOICES
        return context


class SeminarDetailView(DetailView):
    model = Seminar
    template_name = 'seminars/seminar_detail.html'
    context_object_name = 'seminar'

    def get_queryset(self):
        return Seminar.objects.select_related('posted_by', 'university')


class SeminarCreateView(LoginRequiredMixin, CreateView):
    model = Seminar
    form_class = SeminarForm
    template_name = 'seminars/seminar_form.html'
    success_url = reverse_lazy('seminars-list')

    def form_valid(self, form):
        seminar = form.save(commit=False)
        seminar.posted_by = self.request.user
        seminar.save()
        form.save_m2m()
        messages.success(self.request, 'Seminar announcement submitted successfully.')
        return redirect(self.success_url)


def _fetch_universities_for_country(country_name):
    if not country_name:
        return []

    url = f"http://universities.hipolabs.com/search?{urlencode({'country': country_name})}"
    try:
        with urlopen(url, timeout=20) as response:
            payload = response.read().decode('utf-8')
    except Exception:
        return []

    try:
        rows = json.loads(payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []

    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


@require_GET
def universities_by_country(request):
    country_code = (request.GET.get('country') or '').strip().upper()
    valid_codes = {code for code, _ in COUNTRY_CHOICES}
    if country_code not in valid_codes:
        return JsonResponse({'universities': []})

    queryset = University.objects.filter(country_code=country_code).exclude(name__isnull=True).exclude(name='').order_by('name')
    if not queryset.exists():
        country_name = COUNTRY_MAP.get(country_code, '')
        rows = _fetch_universities_for_country(country_name)
        for row in rows:
            name = (row.get('name') or '').strip()
            if not name:
                continue

            websites = row.get('web_pages') or []
            website = str(websites[0]).strip() if isinstance(websites, list) and websites else ''
            domains = row.get('domains') or []
            external_id = str(domains[0]).strip().lower() if isinstance(domains, list) and domains else ''
            if not external_id:
                external_id = f"{name.lower()}::{country_code.lower()}"

            University.objects.update_or_create(
                source='hipolabs',
                external_id=external_id,
                defaults={
                    'name': name,
                    'country_code': country_code,
                    'website': website,
                },
            )

        queryset = University.objects.filter(country_code=country_code).exclude(name__isnull=True).exclude(name='').order_by('name')

    data = [{'id': uni.id, 'name': uni.name} for uni in queryset]
    return JsonResponse({'universities': data})


