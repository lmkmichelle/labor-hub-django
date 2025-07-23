from collections import defaultdict

from django.http import HttpResponse, JsonResponse
from django.template import loader

from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.models import CustomUser
from publications.models import Publication


# Create your views here.
def home(request):
    return render(request, 'core/home.html')


def map_view(request):
    return render(request, 'core/map.html')


@require_GET
def countries_with_users(request):
    country_users = defaultdict(list)

    users = CustomUser.objects.select_related("profile").filter(
        profile__country_code__isnull=False,
        is_active=True
    ).order_by('first_name', 'last_name')

    for user in users:
        country_code = user.profile.country_code.upper()
        country_users[country_code].append({
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email
        })

    return JsonResponse(dict(country_users))


@require_GET
def countries_with_papers(request):
    country_papers = defaultdict(list)

    papers = Publication.objects.filter(
        country_code__isnull=False,
        approved=True
    ).prefetch_related('authors__user').order_by('title')

    for paper in papers:
        author_names = []
        for author in paper.authors.all():
            if author.user:
                author_names.append(f"{author.user.first_name} {author.user.last_name}")
            else:
                author_names.append(author.name)

        country_code = paper.country_code.upper()
        country_papers[country_code].append({
            'title': paper.title,
            'author': ', '.join(author_names) if author_names else 'Unknown Author'
        })
    # for paper in papers:
    #     # Get author names from the paper
    #     author_names = []
    #     for author in paper.authors.all():
    #         if author.user:
    #             author_names.append(f"{author.user.first_name} {author.user.last_name}")
    #         else:
    #             author_names.append(author.name)
    #
    #     country_papers[paper.country_code].append({
    #         'title': paper.title,
    #         'author': ', '.join(author_names) if author_names else 'Unknown Author'
    #     })

    return JsonResponse(dict(country_papers))
