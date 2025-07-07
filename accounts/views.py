from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from publications.models import Publication


@login_required
def profile(request):
    user = request.user
    authored_publications = Publication.objects.filter(
        authors__user=user
    ).distinct().prefetch_related('authors__user')

    return render(request, 'accounts/profile.html', {
        'user': user,
        'publications': authored_publications
    })
