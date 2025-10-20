from django.urls import path

from seminars.views import SeminarsListView

urlpatterns = [
    path('', SeminarsListView.as_view(), name='seminars-list'),
    # path('create/', EventCreateView.as_view(), name='event-create'),
    # path('<int:pk>/', EventsDetailView.as_view(), name='event-detail'),
]
