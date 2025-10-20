from django.views.generic import ListView
from django.shortcuts import render
from django.db.models import Q
from django.utils import timezone

from seminars.models import Seminar


class SeminarsListView(ListView):
    model = Seminar
    template_name = 'seminars/seminars_list.html'
    context_object_name = 'seminars'
    paginate_by = 10

    def get_queryset(self):
        queryset = Seminar.objects.all().order_by('-date')

        # Search functionality
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(host__first_name__icontains=query) |
                Q(host__last_name__icontains=query) |
                Q(location__icontains=query)
            )

        # Filter functionality
        filter_type = self.request.GET.get('filter')
        if filter_type == 'upcoming':
            queryset = queryset.filter(date__gte=timezone.now())
        elif filter_type == 'past':
            queryset = queryset.filter(date__lt=timezone.now())

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add search filters for the search form
        context['seminar_filters'] = [
            {'value': '', 'label': 'All Seminars'},
            {'value': 'upcoming', 'label': 'Upcoming'},
            {'value': 'past', 'label': 'Past'},
        ]

        # Pass current search query and filter
        context['query'] = self.request.GET.get('q', '')
        context['filter_type'] = self.request.GET.get('filter', '')

        return context
