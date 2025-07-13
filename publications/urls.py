from django.urls import path
from . import views
from .views import PublicationListView, PublicationCreateView, PublicationDetailView, PublicationUpdateView

urlpatterns = [
    path('', PublicationListView.as_view(), name='publications'),
    path('<int:pk>/', PublicationDetailView.as_view(), name='publication_detail'),
    path('edit/<int:pk>/', PublicationUpdateView.as_view(), name='edit_publication'),
    path('upload/', PublicationCreateView.as_view(), name='upload_publication'),
]
