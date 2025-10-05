from django.urls import path
from events.views import EventsListView, EventCreateView

urlpatterns = [
    path('', EventsListView.as_view(), name='events-list'),
    path('create/', EventCreateView.as_view(), name='event-create'),
]
