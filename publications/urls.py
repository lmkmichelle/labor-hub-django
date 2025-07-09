from django.urls import path
from . import views

urlpatterns = [
    path('', views.publications, name='publications'),
    path('<int:pk>/', views.publication_detail, name='publication_detail'),
    path('upload/', views.upload_publication, name='upload_publication'),
]
