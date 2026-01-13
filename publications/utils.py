import json

from accounts.models import CustomUser
from .models import Author

def handle_authors(raw_input):
    authors = []
    for entry in json.loads(raw_input):
        name = entry['value']
        user_id = entry.get('id')
        if user_id:
            try:
                user = CustomUser.objects.get(id=user_id)
                author, _ = Author.objects.get_or_create(
                    user=user,
                    defaults={ 'name': name or user.get_full_name() }
                )
            except CustomUser.DoesNotExist:
                author, _ = Author.objects.get_or_create(user=None, name=name)
        else:
            matching_user = None
            name_parts = name.split()

            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:])

                matching_user = CustomUser.objects.filter(
                    first_name__iexact=first_name,
                    last_name__iexact=last_name
                ).first()

            if matching_user:
                author, _ = Author.objects.get_or_create(
                    user=matching_user,
                    defaults={'name': name}
                )
            else:
                author, _ = Author.objects.get_or_create(
                    user=None,
                    name=name
                )

        authors.append(author)
    return authors


def handle_keywords(raw_input):
    keywords = []
    for entry in json.loads(raw_input):
        keywords.append(entry)
    return keywords

def process_publication_form(request, form):
    publication = form.save(commit=False)

    raw_keywords = request.POST.get('keywords_input', '[]')
    publication.keywords = handle_keywords(raw_keywords)
    
    topic_input = request.POST.get('topic_input', '')
    publication.topic = topic_input

    publication.save()

    raw_authors = request.POST.get('authors_input', '[]')
    publication.authors.set(handle_authors(raw_authors))

    return publication
