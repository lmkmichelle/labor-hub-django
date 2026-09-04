from django.urls import path

from seminars.views import (
    SeminarCreateView,
    SeminarDeleteView,
    SeminarDetailView,
    SeminarsListView,
    universities_by_country,
)

urlpatterns = [
    path('', SeminarsListView.as_view(), name='seminars-list'),
    path('create/', SeminarCreateView.as_view(), name='seminar-create'),
    path('universities/', universities_by_country, name='seminar-universities'),
    path('<int:pk>/', SeminarDetailView.as_view(), name='seminar-detail'),
    path('<int:pk>/delete/', SeminarDeleteView.as_view(), name='visit-delete'),
]
