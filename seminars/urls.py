from django.urls import path

from seminars.views import SeminarDetailView, SeminarsListView, register_seminar_interest

urlpatterns = [
    path('', SeminarsListView.as_view(), name='seminars-list'),
    path('<int:pk>/', SeminarDetailView.as_view(), name='seminar-detail'),
    path('<int:pk>/interest/', register_seminar_interest, name='seminar-interest'),
]
