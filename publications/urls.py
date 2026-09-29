from django.urls import path

from .views import (
    AdvisedPapersView,
    PublicationCreateView,
    PublicationDetailView,
    PublicationUpdateView,
    paper_ack_confirm,
    paper_ack_decline,
    publication_bibtex,
    publication_download,
)

urlpatterns = [
    path('advising/', AdvisedPapersView.as_view(), name='advised_papers'),
    path('advising/<int:pk>/confirm/', paper_ack_confirm, name='paper_ack_confirm'),
    path('advising/<int:pk>/decline/', paper_ack_decline, name='paper_ack_decline'),
    path('<int:pk>/', PublicationDetailView.as_view(), name='publication_detail'),
    path('<int:pk>/cite/', publication_bibtex, name='publication_bibtex'),
    path('<int:pk>/download/', publication_download, name='publication_download'),
    path('edit/<int:pk>/', PublicationUpdateView.as_view(), name='edit_publication'),
    path('submit/', PublicationCreateView.as_view(), name='submit_paper'),
]
