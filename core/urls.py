from django.urls import include, path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('map/', views.map_view, name='map'),
]
