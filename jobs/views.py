from datetime import datetime

from django.db.models import Q
from django.views.generic import DetailView, ListView

from .models import Job


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

		sort = self.request.GET.get('sort', 'deadline')
		if sort == 'newest':
			queryset = queryset.order_by('-id')
		else:
			queryset = queryset.order_by('deadline', '-id')

		return queryset

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['query'] = self.request.GET.get('q', '')
		context['deadline_from'] = self.request.GET.get('deadline_from', '')
		context['deadline_to'] = self.request.GET.get('deadline_to', '')
		context['sort'] = self.request.GET.get('sort', 'deadline')
		return context


class JobDetailView(DetailView):
	model = Job
	template_name = 'jobs/job_detail.html'
	context_object_name = 'job'
