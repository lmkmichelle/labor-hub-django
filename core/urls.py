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
    path('api/map/summary/', views.map_summary, name='map_summary'),
    path('api/map/country/<str:code>/', views.map_country_detail, name='map_country_detail'),
]
