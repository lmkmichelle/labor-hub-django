from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView

from core.views import OwnerDeleteView

from .forms import SpecialIssueForm
from .models import SpecialIssue


class SpecialIssuesListView(ListView):
    model = SpecialIssue
    template_name = 'special_issues/special_issue_list.html'
    context_object_name = 'special_issues'
    paginate_by = 10

    def get_queryset(self):
        queryset = SpecialIssue.objects.approved().select_related('posted_by')

        show_closed = self.request.GET.get('show_closed') == '1'
        today = timezone.localdate()
        if show_closed:
            queryset = queryset.filter(submission_deadline__lt=today)
        else:
            queryset = queryset.filter(submission_deadline__gte=today)

        query = self.request.GET.get('q', '').strip()
        if query:
            # editors is JSON text; icontains on it matches editor names.
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(journal__icontains=query) |
                Q(description__icontains=query) |
                Q(editors__icontains=query)
            )

        if self.request.GET.get('sort') == 'newest':
            return queryset.order_by('-created_at', '-id')
        if show_closed:
            return queryset.order_by('-submission_deadline', '-id')
        return queryset.order_by('submission_deadline', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        context['show_closed'] = self.request.GET.get('show_closed') == '1'
        context['sort'] = self.request.GET.get('sort', '')

        filter_params = {}
        if context['query']:
            filter_params['q'] = context['query']
        if context['show_closed']:
            filter_params['show_closed'] = '1'
        if context['sort']:
            filter_params['sort'] = context['sort']
        context['filter_querystring'] = urlencode(filter_params)
        return context


class SpecialIssueDetailView(DetailView):
    model = SpecialIssue
    template_name = 'special_issues/special_issue_detail.html'
    context_object_name = 'special_issue'

    def get_queryset(self):
        return SpecialIssue.objects.select_related('posted_by')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.is_approved:
            return obj
        user = self.request.user
        if user.is_authenticated and obj.posted_by_id == user.id:
            return obj
        raise Http404("This special issue is not available.")


class SpecialIssueCreateView(LoginRequiredMixin, CreateView):
    """Fellows (researchers) only: a special issue needs a fellow as an editor."""

    model = SpecialIssue
    form_class = SpecialIssueForm
    template_name = 'special_issues/special_issue_form.html'
    success_url = reverse_lazy('special-issues-list')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_researcher():
            raise PermissionDenied("Only fellows can post a special issue.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        special_issue = form.save(commit=False)
        special_issue.posted_by = self.request.user
        special_issue.status = 'pending'
        special_issue.save()
        messages.success(
            self.request,
            'Special issue submitted successfully! It will be visible once approved by an administrator.',
        )
        return redirect(self.success_url)


class SpecialIssueDeleteView(OwnerDeleteView):
    model = SpecialIssue
    owner_field = 'posted_by'
    success_url = reverse_lazy('special-issues-list')
    success_message = 'Your special issue has been deleted.'
