from django.urls import path
from events.views import EventsListView

urlpatterns = [
    path('', EventsListView.as_view(), name='events-list'),
]
