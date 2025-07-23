from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView, CreateView, UpdateView
from publications.forms import PublicationForm
from publications.models import Publication
from .utils import process_publication_form

class PublicationDetailView(DetailView):
    model = Publication
    template_name = 'publications/publication_detail.html'
    context_object_name = 'publication'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)

        if obj.approved:
            return obj

        authors_users = [author.user for author in obj.authors.all() if author.user]

        if self.request.user.is_authenticated and self.request.user in authors_users:
            return obj

        raise Http404("This publication is not available.")


class PublicationCreateView(CreateView):
    model = Publication
    form_class = PublicationForm
    template_name = 'publications/publication_form.html'

    def form_valid(self, form):
        process_publication_form(self.request, form)
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
