from collections import defaultdict
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.views.generic import ListView

from accounts.models import CustomUser
from core.constants import COUNTRY_CHOICES
from publications.models import Publication

country_name_to_code = {name.lower(): code for code, name in COUNTRY_CHOICES}

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
            'position': user.profile.position,
            'education': user.profile.education,
            'email': user.email
        })

    return JsonResponse(dict(country_users))


@require_GET
def countries_with_papers(request):
    country_papers = defaultdict(list)

    papers = Publication.objects.filter(
        country_code__isnull=False,
        status='approved'
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

    return JsonResponse(dict(country_papers))

class UserListView(ListView):
    model = CustomUser
    template_name = 'accounts/users_list.html'
    context_object_name = 'users'
    paginate_by = 10

    role = None

    def get_queryset(self):
        qs = CustomUser.objects.filter(is_active=True, role=self.role).select_related('profile')

        query = self.request.GET.get('q', '')
        filter_type = self.request.GET.get('filter', 'all')

        if query:
            if filter_type == 'name':
                qs = qs.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query))
            elif filter_type == 'email':
                qs = qs.filter(email__icontains=query)
            elif filter_type == 'country':
                matching_codes = [
                    code for code, name in COUNTRY_CHOICES
                    if query.strip().lower() in name.lower()
                ]
                if matching_codes:
                    qs = qs.filter(profile__country_code__in=matching_codes)
                else:
                    qs = qs.filter(profile__country_code__iexact=query)
            elif filter_type == 'position':
                qs = qs.filter(profile__position__icontains=query)
            elif filter_type == 'research_interests':
                qs = qs.filter(profile__research_interests__icontains=query)
            else:
                qs = qs.filter(
                    Q(first_name__icontains=query) |
                    Q(last_name__icontains=query) |
                    Q(email__icontains=query) |
                    Q(profile__position__icontains=query) |
                    Q(profile__country_code__icontains=query) |
                    Q(profile__research_interests__icontains=query))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['COUNTRY_CHOICES'] = COUNTRY_CHOICES
        context['query'] = self.request.GET.get('q', '')
        context['filter_type'] = self.request.GET.get('filter', 'all')
        context['countries'] = dict(COUNTRY_CHOICES)
        context['user_filters'] = [
            {'value': 'all', 'label': 'All Fields'},
            {'value': 'name', 'label': 'Name'},
            {'value': 'country', 'label': 'Country'},
            {'value': 'position', 'label': 'Position'},
            {'value': 'research_interests', 'label': 'Research Interests'},
        ]
        return context

class ResearchersListView(UserListView):
    role = CustomUser.Role.RESEARCHER

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_type'] = 'researcher'
        return context

class StudentsListView(UserListView):
    role = CustomUser.Role.STUDENT

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_type'] = 'student'
        return context

@require_GET
def search_accounts(request):
    query = request.GET.get('q', '')
    users = CustomUser.objects.filter(first_name__icontains=query)[:10]
    return JsonResponse([
        {'value': f"{u.first_name} {u.last_name}", 'id': str(u.id)}
        for u in users
    ], safe=False)

@require_GET
def publications_list(request):
    publications = Publication.objects.filter(status='approved').prefetch_related('authors__user')

    query = request.GET.get('q', '')
    filter_type = request.GET.get('filter', 'all')

    publication_filters = [
        {'value': 'all', 'label': 'All'},
        {'value': 'title', 'label': 'Title'},
        {'value': 'authors', 'label': 'Authors'},
        {'value': 'country', 'label': 'Country'},
        {'value': 'keywords', 'label': 'Keywords'},
    ]

    if query:
        if filter_type == 'title':
            publications = publications.filter(title__icontains=query)
        elif filter_type == 'authors':
            publications = publications.filter(
                Q(authors__name__icontains=query) |
                Q(authors__user__first_name__icontains=query) |
                Q(authors__user__last_name__icontains=query))
        elif filter_type == 'country':
            matching_codes = [
                code for code, name in COUNTRY_CHOICES
                if query.strip().lower() in name.lower()
            ]
            if matching_codes:
                publications = publications.filter(country_code__in=matching_codes)
            else:
                publications = publications.filter(country_code__iexact=query)
        elif filter_type == 'keywords':
            publications = publications.filter(keywords__icontains=query)
        else:
            publications = publications.filter(
                Q(title__icontains=query) |
                Q(authors__name__icontains=query) |
                Q(authors__user__first_name__icontains=query) |
                Q(authors__user__last_name__icontains=query) |
                Q(abstract__icontains=query) |
                Q(country_code__icontains=query) |
                Q(keywords__icontains=query) |
                Q(study_url__icontains=query) |
                Q(is_job_market__icontains=query)).distinct()

    paginator = Paginator(publications, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    countries = dict(COUNTRY_CHOICES)

    return render(request, 'publications/publications.html', {
        'publications': page_obj,
        'COUNTRY_CHOICES': COUNTRY_CHOICES,
        'query': query,
        'filter_type': filter_type,
        'countries': countries,
        'publication_filters': publication_filters,
    })
