from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Case, IntegerField, When
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, CreateView, ListView, UpdateView

from publications.emails import send_paper_advisor_ack_email
from publications.forms import PublicationForm
from publications.models import Publication
from .utils import process_publication_form

class PublicationDetailView(DetailView):
    model = Publication
    template_name = 'publications/publication_detail.html'
    context_object_name = 'publication'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)

        if obj.status == 'approved':
            return obj

        authors_users = [author.user for author in obj.authors.all() if author.user]

        if self.request.user.is_authenticated and self.request.user in authors_users:
            return obj

        raise Http404("This publication is not available.")


class PublicationCreateView(LoginRequiredMixin, CreateView):
    model = Publication
    form_class = PublicationForm
    template_name = 'publications/publication_form.html'

    def form_valid(self, form):
        publication = process_publication_form(self.request, form)
        if publication.is_job_market and publication.jm_advisor_id:
            send_paper_advisor_ack_email(publication)
        return redirect(reverse_lazy('publications'))


class PublicationUpdateView(LoginRequiredMixin, UpdateView):
    model = Publication
    form_class = PublicationForm
    template_name = 'publications/publication_form.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)

        user_full_name = self.request.user.get_full_name()
        is_author = (
                obj.authors.filter(user=self.request.user).exists() or
                obj.authors.filter(name=user_full_name).exists()
        )

        if not is_author:
            raise Http404("You don't have permission to edit this publication.")

        return obj

    def form_valid(self, form):
        process_publication_form(self.request, form)
        return redirect(reverse_lazy('publications'))

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        publication_form = PublicationForm(request.POST, request.FILES, instance=self.object)

        if publication_form.is_valid():
            process_publication_form(self.request, publication_form)
            messages.success(request, "Paper updated successfully.")
            return redirect("publications")

        return self.render_to_response(self.get_context_data(form=publication_form))


class AdvisedPapersView(LoginRequiredMixin, ListView):
    """Job market papers naming the logged-in researcher as advisor.

    The advisor confirms or declines here; the response is recorded on the
    paper for the Labor Hub team to review.
    """
    template_name = 'publications/advised_papers.html'
    context_object_name = 'papers'
    paginate_by = 12

    def get_queryset(self):
        return (
            Publication.objects.filter(
                jm_advisor=self.request.user, is_job_market=True)
            .select_related('submitted_by')
            .prefetch_related('authors__user')
            .annotate(
                _pending_first=Case(
                    When(jm_advisor_acknowledged__isnull=True, then=0),
                    default=1,
                    output_field=IntegerField(),
                )
            )
            .order_by('_pending_first', '-applied_at')
        )


def _get_own_advised_paper(request, pk):
    """The jm_advisor filter IS the authorization check; a wrong user gets a 404."""
    return get_object_or_404(
        Publication, pk=pk, jm_advisor=request.user, is_job_market=True,
    )


def _record_response(request, pk, acknowledged):
    paper = _get_own_advised_paper(request, pk)
    if paper.has_advisor_response:
        messages.error(request, "You have already responded to this paper.")
    else:
        paper.jm_advisor_acknowledged = acknowledged
        paper.jm_advisor_responded_at = timezone.now()
        paper.save(update_fields=[
            'jm_advisor_acknowledged', 'jm_advisor_responded_at'])
        messages.success(
            request,
            "Thanks - your response has been recorded."
            if acknowledged else "Recorded that you declined this paper.",
        )
    return redirect('advised_papers')


@login_required
@require_POST
def paper_ack_confirm(request, pk):
    return _record_response(request, pk, True)


@login_required
@require_POST
def paper_ack_decline(request, pk):
    return _record_response(request, pk, False)
