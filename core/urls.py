from django.urls import include, path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('map/', views.map_view, name='map'),
    path('users/', views.users_list, name='users_list'),
    path('publications/', views.publications_list, name='publications_list'),
    path('api/countries-with-users/', views.countries_with_users, name='countries_with_users'),
    path('api/countries-with-papers/', views.countries_with_papers, name='countries_with_papers'),

]
