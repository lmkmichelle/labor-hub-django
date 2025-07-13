import json

from django.contrib import messages
from django.http import Http404
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.shortcuts import render, redirect
from django.db.models import Q
from .utils import process_publication_form

from publications.forms import PublicationForm
from publications.models import Publication, Author


class PublicationListView(ListView):
    model = Publication
    template_name = 'publications/publications.html'
    context_object_name = 'publications'

    def get_queryset(self):
        query = self.request.GET.get('q')
        queryset = Publication.objects.prefetch_related('authors__user').filter(approved=True)

        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(abstract__icontains=query) |
                Q(country__icontains=query) |
                Q(keywords__icontains=query) |
                Q(authors__name__icontains=query)
            ).distinct()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        return context


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


class PublicationUpdateView(UpdateView):
    model = Publication
    form_class = PublicationForm
    template_name = 'publications/publication_form.html'

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
