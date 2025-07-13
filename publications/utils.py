import json
from .models import Author

def handle_authors(raw_input):
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


def handle_keywords(raw_input):
    keywords = []
    for entry in json.loads(raw_input):
        keyword = entry['value']
        keywords.append(keyword)
    return keywords

def process_publication_form(request, form):
    publication = form.save(commit=False)

    raw_keywords = request.POST.get('keywords_input', '[]')
    publication.keywords = handle_keywords(raw_keywords)

    publication.save()

    raw_authors = request.POST.get('authors_input', '[]')
    publication.authors.set(handle_authors(raw_authors))

    return publication
