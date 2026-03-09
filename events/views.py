from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, DetailView
from django.db.models import Q
from datetime import datetime

from .models import Event
from .forms import EventForm


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


class EventsListView(ListView):
    model = Event
    template_name = 'events/event_list.html'
    context_object_name = 'events'
    paginate_by = 10

    def get_queryset(self):
        queryset = Event.objects.filter(
            status='approved',
        )

        # Search query
        query = self.request.GET.get('q', '')
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(location__icontains=query)
            )

        # Category filter
        categories = self.request.GET.getlist('category')
        if categories:
            queryset = queryset.filter(category__in=categories)

        # Date range filter
        start_date = _parse_date(self.request.GET.get('start_date'))
        end_date = _parse_date(self.request.GET.get('end_date'))

        if start_date:
            queryset = queryset.filter(date__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__date__lte=end_date)

        sort = self.request.GET.get('sort', '')
        if sort == 'deadline':
            queryset = queryset.filter(deadline__isnull=False).order_by('deadline')
        else:
            queryset = queryset.order_by('date')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        context['selected_categories'] = self.request.GET.getlist('category')
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        context['category_choices'] = Event.CATEGORY_CHOICES
        context['sort'] = self.request.GET.get('sort', '')
        return context

class EventsDetailView(DetailView):
    model = Event
    template_name = 'events/event_detail.html'
    context_object_name = 'event'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)

        if obj.status == 'approved':
            return obj

        if self.request.user.is_authenticated and self.request.user == obj.host:
            return obj

        raise Http404("This event is not available.")

class EventCreateView(LoginRequiredMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'
    success_url = reverse_lazy('events-list')

    def form_valid(self, form):
        event = form.save(commit=False)
        event.host = self.request.user
        event.status = 'pending'
        event.save()
        messages.success(self.request, 'Event submitted successfully! It will be visible once approved by an administrator.')
        return redirect(self.success_url)
