from django.urls import include, path
from . import views
from .views import StudentsListView, ResearchersListView

urlpatterns = [
    path('', views.home, name='home'),
    path('map/', views.map_view, name='map'),
    path('researchers/', ResearchersListView.as_view(), name='researchers'),
    path('students/', StudentsListView.as_view(), name='students'),
    path('publications/', views.publications_list, name='publications'),
    path('api/accounts/search/', views.search_accounts, name='search_accounts'),
    path('api/countries-with-users/', views.countries_with_users, name='countries_with_users'),
    path('api/countries-with-papers/', views.countries_with_papers, name='countries_with_papers'),
]
