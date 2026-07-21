from datetime import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView

from core.constants import COUNTRY_CHOICES

from .forms import JobForm
from .models import JUNIOR_RANKS, RANK_CHOICES, Job


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


def _parse_date(value):
    """Parse a date string in either MM/DD/YYYY or YYYY-MM-DD format."""
    if not value:
        return None
    for fmt in ('%m/%d/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


class JobsListView(ListView):
    model = Job
    template_name = 'jobs/job_list.html'
    context_object_name = 'jobs'
    paginate_by = 10

    def get_queryset(self):
        queryset = Job.objects.select_related('uploader').all()

        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query)
            )

        deadline_from = _parse_date(self.request.GET.get('deadline_from'))
        deadline_to = _parse_date(self.request.GET.get('deadline_to'))

        if deadline_from:
            queryset = queryset.filter(deadline__gte=deadline_from)
        if deadline_to:
            queryset = queryset.filter(deadline__lte=deadline_to)

        country_terms = _parse_country_terms(self.request.GET.get('countries', ''))
        selected_countries = _map_country_terms_to_codes(country_terms)
        if not selected_countries:
            selected_countries = [code for code in self.request.GET.getlist('country') if code]
        if selected_countries:
            matching_ids = []
            for job in queryset:
                countries = job.countries or []
                if any(code in countries for code in selected_countries):
                    matching_ids.append(job.id)
            queryset = queryset.filter(id__in=matching_ids)

        # Rank/title filter. The sidebar sends explicit `category` values; the
        # nav's junior/student link sends `audience=students`, which maps to the
        # junior ranks (predoc + postdoc). Categories live in a JSONField, so we
        # match in Python for cross-database consistency.
        valid_ranks = {code for code, _ in RANK_CHOICES}
        required_categories = {c for c in self.request.GET.getlist('category') if c in valid_ranks}
        if self.request.GET.get('audience', '').strip().lower() == 'students':
            required_categories.update(JUNIOR_RANKS)
        if required_categories:
            matching_ids = [
                job.id for job in queryset
                if required_categories & set(job.categories or [])
            ]
            queryset = queryset.filter(id__in=matching_ids)

        sort = self.request.GET.get('sort', 'deadline')
        if sort == 'newest':
            queryset = queryset.order_by('-id')
        elif sort == 'location':
            jobs = list(queryset)
            jobs.sort(key=lambda job: (job.country_labels()[0].lower() if job.country_labels() else '\uffff'))
            return jobs
        else:
            queryset = queryset.order_by('deadline', '-id')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        country_terms = _parse_country_terms(self.request.GET.get('countries', ''))
        selected_countries = _map_country_terms_to_codes(country_terms)
        if not selected_countries:
            selected_countries = [code for code in self.request.GET.getlist('country') if code]

        context['query'] = self.request.GET.get('q', '')
        context['deadline_from'] = self.request.GET.get('deadline_from', '')
        context['deadline_to'] = self.request.GET.get('deadline_to', '')
        context['sort'] = self.request.GET.get('sort', 'deadline')
        context['audience'] = self.request.GET.get('audience', '').strip().lower()
        context['selected_countries'] = selected_countries
        context['selected_countries_serialized'] = ','.join(selected_countries)
        context['country_choices'] = COUNTRY_CHOICES

        valid_ranks = {code for code, _ in RANK_CHOICES}
        selected_categories = [c for c in self.request.GET.getlist('category') if c in valid_ranks]
        context['selected_categories'] = selected_categories
        context['rank_choices'] = RANK_CHOICES

        filter_params = {}
        if context['query']:
            filter_params['q'] = context['query']
        if context['selected_countries_serialized']:
            filter_params['countries'] = context['selected_countries_serialized']
        if context['deadline_from']:
            filter_params['deadline_from'] = context['deadline_from']
        if context['deadline_to']:
            filter_params['deadline_to'] = context['deadline_to']
        if context['audience']:
            filter_params['audience'] = context['audience']
        if selected_categories:
            filter_params['category'] = selected_categories
        if context['sort']:
            filter_params['sort'] = context['sort']
        context['filter_querystring'] = urlencode(filter_params, doseq=True)
        return context


class JobDetailView(DetailView):
    model = Job
    template_name = 'jobs/job_detail.html'
    context_object_name = 'job'


class JobCreateView(LoginRequiredMixin, CreateView):
    model = Job
    form_class = JobForm
    template_name = 'jobs/job_form.html'
    success_url = reverse_lazy('jobs-list')

    def form_valid(self, form):
        job = form.save(commit=False)
        job.uploader = self.request.user
        job.save()
        form.save_m2m()
        messages.success(self.request, 'Job posted successfully.')
        return redirect(self.success_url)

