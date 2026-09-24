from django.urls import path

from .views import (
    SpecialIssueCreateView,
    SpecialIssueDeleteView,
    SpecialIssueDetailView,
    SpecialIssuesListView,
)

urlpatterns = [
    path('', SpecialIssuesListView.as_view(), name='special-issues-list'),
    path('create/', SpecialIssueCreateView.as_view(), name='special-issue-create'),
    path('<int:pk>/', SpecialIssueDetailView.as_view(), name='special-issue-detail'),
    path('<int:pk>/delete/', SpecialIssueDeleteView.as_view(), name='special-issue-delete'),
]
