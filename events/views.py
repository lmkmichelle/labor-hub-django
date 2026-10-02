from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, DetailView, UpdateView
from django.db.models import Q
from django.db.models.functions import Lower
from datetime import datetime

from core.constants import ADMIN1_LABELS, DEFAULT_ADMIN1_LABEL
from core.views import OwnerDeleteView

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
        elif sort == 'location':
            queryset = queryset.order_by(Lower('location'), 'date')
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

class LocationPickerContextMixin:
    """Drives the State/Province field's label per country in
    static/js/location-picker.js; single source of truth is
    core.constants.ADMIN1_LABELS. Shared by the create and edit views."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['admin1_labels'] = ADMIN1_LABELS
        context['default_admin1_label'] = DEFAULT_ADMIN1_LABEL
        return context


class EventCreateView(LoginRequiredMixin, LocationPickerContextMixin, CreateView):
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


class EventUpdateView(LoginRequiredMixin, LocationPickerContextMixin, UpdateView):
    """Lets a host edit their own event. Status/host are left untouched, so an
    already-approved event stays visible -- it doesn't go back to pending,
    the same way an approved publication edit stays approved."""
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'

    def get_queryset(self):
        return super().get_queryset().filter(host=self.request.user)

    def get_success_url(self):
        return reverse_lazy('event-detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Event updated successfully.')
        return response


class EventDeleteView(OwnerDeleteView):
    model = Event
    owner_field = 'host'
    success_url = reverse_lazy('events-list')
    success_message = 'Your event has been deleted.'
