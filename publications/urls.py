from django.urls import path
from .views import PublicationCreateView, PublicationDetailView, PublicationUpdateView

urlpatterns = [
    path('<int:pk>/', PublicationDetailView.as_view(), name='publication_detail'),
    path('edit/<int:pk>/', PublicationUpdateView.as_view(), name='edit_publication'),
    path('submit/', PublicationCreateView.as_view(), name='submit_paper'),
]
