import json

from django.shortcuts import render, redirect
from django.db.models import Q

from publications.forms import PublicationForm
from publications.models import Publication, Author


def publications(request):
    query = request.GET.get('q', '')
    publications_list = Publication.objects.all().prefetch_related('authors__user')

    if query:
        publications_list = publications_list.filter(
            Q(title__icontains=query) |
            Q(abstract__icontains=query) |
            Q(country__icontains=query) |
            Q(keywords__icontains=query) |
            Q(authors__name__icontains=query)
        ).distinct()

    return render(request, 'publications/publications.html', {
        'publications': publications_list,
        'query': query
    })


def publication_detail(request, pk):
    publication = Publication.objects.get(pk=pk)
    return render(request, 'publications/publication_detail.html', {'publication': publication})


def handle_authors_input(raw_input):
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


def upload_publication(request):
    if request.method == 'POST':
        form = PublicationForm(request.POST, request.FILES)
        if form.is_valid():
            publication = form.save(commit=False)
            publication.save()

            raw_authors = request.POST.get('authors_input', '[]')
            authors = handle_authors_input(raw_authors)
            publication.authors.set(authors)

            return redirect('/publications/')

    else:
        form = PublicationForm()
    return render(request, 'publications/publication_form.html', {'form': form})
