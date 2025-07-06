from django.shortcuts import render

from publications.models import Publication

def publications(request):
    publications_list = Publication.objects.all().prefetch_related('authors__user')
    return render(request, 'publications/publications.html', {'publications': publications_list})

def publication_detail(request, pk):
    publication = Publication.objects.get(pk=pk)
    return render(request, 'publications/publication_detail.html', {'publication': publication})
