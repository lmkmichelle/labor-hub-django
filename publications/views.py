import json

from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView
from django.shortcuts import render, redirect
from django.db.models import Q

from publications.forms import PublicationForm
from publications.models import Publication, Author

class PublicationListView(ListView):
    model = Publication
    template_name = 'publications/publications.html'
    context_object_name = 'publications'

    def get_queryset(self):
        query = self.request.GET.get('q')
        queryset = Publication.objects.prefetch_related('authors__user')

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

class PublicationCreateView(CreateView):
    model = Publication
    form_class = PublicationForm
    template_name = 'publications/publication_form.html'

    def form_valid(self, form):
        publication = form.save(commit=False)

        raw_keywords = self.request.POST.get('keywords_input', '[]')
        publication.keywords = self._handle_keywords(raw_keywords)

        publication.save()

        raw_authors = self.request.POST.get('authors_input', '[]')
        publication.authors.set(self._handle_authors(raw_authors))

        return redirect(reverse_lazy('publications'))

    @staticmethod
    def _handle_authors(raw_input):
        authors = []
        for entry in json.loads(raw_input):
            name = entry['value']
            user_id = entry.get('id')
            if user_id:
                author, _ = Author.objects.get_or_create(user_id=user_id, name="")
            else:
                author, _ = Author.objects.get_or_create(user=None, name=name)
            authors.append(author)

        return authors

    @staticmethod
    def _handle_keywords(raw_input):
        keywords = []
        for entry in json.loads(raw_input):
            keyword = entry['value']
            keywords.append(keyword)

        return keywords


# def upload_publication(request):
#     if request.method == 'POST':
#         form = PublicationForm(request.POST, request.FILES)
#         if form.is_valid():
#             publication = form.save(commit=False)
#
#             raw_keywords = request.POST.get('keywords_input', '[]')
#             keywords = keywords_input(raw_keywords)
#             publication.keywords = keywords
#
#             publication.save()
#
#             raw_authors = request.POST.get('authors_input', '[]')
#             authors = authors_input(raw_authors)
#             publication.authors.set(authors)
#
#             publication.save()
#
#             return redirect('/publications/')
#     else:
#         form = PublicationForm()
#     return render(request, 'publications/publication_form.html', {'form': form})
