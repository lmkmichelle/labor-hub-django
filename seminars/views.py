from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView
from core.constants import COUNTRY_CHOICES

from seminars.models import Seminar, SeminarInterest


class SeminarsListView(ListView):
    model = Seminar
    template_name = 'seminars/seminars_list.html'
    context_object_name = 'seminars'
    paginate_by = 10

    def get_queryset(self):
        queryset = Seminar.objects.select_related('host').annotate(
            interested_count=Count('interests', distinct=True)
        )

        show_archived = self.request.GET.get('show_archived') == '1'
        now = timezone.now()
        if show_archived:
            queryset = queryset.filter(date__lt=now)
        else:
            queryset = queryset.filter(date__gte=now)

        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(host__first_name__icontains=query) |
                Q(host__last_name__icontains=query)
            )

        selected_countries = self.request.GET.getlist('country')
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
                queryset = queryset.order_by('-date', '-id')
            else:
                queryset = queryset.order_by('date', '-id')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        context['show_archived'] = self.request.GET.get('show_archived') == '1'
        context['sort'] = self.request.GET.get('sort', '')
        context['selected_countries'] = self.request.GET.getlist('country')
        context['country_choices'] = COUNTRY_CHOICES
        context['next_url'] = self.request.get_full_path()
        return context


class SeminarDetailView(DetailView):
    model = Seminar
    template_name = 'seminars/seminar_detail.html'
    context_object_name = 'seminar'

    def get_queryset(self):
        return Seminar.objects.select_related('host').annotate(
            interested_count=Count('interests', distinct=True)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['next_url'] = self.request.get_full_path()
        return context


@require_POST
def register_seminar_interest(request, pk):
    seminar = get_object_or_404(Seminar, pk=pk)
    next_url = request.POST.get('next') or seminar.get_absolute_url()

    if request.user.is_authenticated:
        _, created = SeminarInterest.objects.get_or_create(
            seminar=seminar,
            user=request.user,
            defaults={
                'guest_name': request.user.get_full_name() or request.user.email,
                'guest_email': request.user.email,
            },
        )
        if created:
            messages.success(request, 'You are now marked as interested in this seminar.')
        else:
            messages.info(request, 'You have already marked interest in this seminar.')
        return redirect(next_url)

    guest_name = request.POST.get('guest_name', '').strip()
    guest_email = request.POST.get('guest_email', '').strip().lower()

    if not guest_name or not guest_email:
        messages.error(request, 'Please provide your name and email to mark interest.')
        return redirect(next_url)

    existing = SeminarInterest.objects.filter(
        seminar=seminar,
        guest_email__iexact=guest_email,
        user__isnull=True,
    ).first()

    if existing:
        messages.info(request, 'This email has already been marked as interested.')
        return redirect(next_url)

    SeminarInterest.objects.create(
        seminar=seminar,
        guest_name=guest_name,
        guest_email=guest_email,
    )
    messages.success(request, 'Thanks! We recorded your interest in this seminar.')

    return redirect(next_url)
