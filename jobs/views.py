from datetime import datetime

from django.db.models import Q
from django.views.generic import DetailView, ListView

from core.constants import COUNTRY_CHOICES

from .models import Job


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

		audience = self.request.GET.get('audience', '').strip().lower()
		if audience == 'students':
			queryset = queryset.filter(is_for_graduate_students=True)

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

		sort = self.request.GET.get('sort', 'deadline')
		if sort == 'newest':
			queryset = queryset.order_by('-id')
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
		return context


class JobDetailView(DetailView):
	model = Job
	template_name = 'jobs/job_detail.html'
	context_object_name = 'job'
