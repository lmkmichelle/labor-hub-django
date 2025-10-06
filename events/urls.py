from django.urls import path
from events.views import EventsListView, EventCreateView, EventsDetailView

urlpatterns = [
    path('', EventsListView.as_view(), name='events-list'),
    path('create/', EventCreateView.as_view(), name='event-create'),
    path('<int:pk>/', EventsDetailView.as_view(), name='event-detail'),
]
