from django.urls import path
from events.views import EventsListView, EventCreateView, EventsDetailView, EventDeleteView

urlpatterns = [
    path('', EventsListView.as_view(), name='events-list'),
    path('create/', EventCreateView.as_view(), name='event-create'),
    path('<int:pk>/', EventsDetailView.as_view(), name='event-detail'),
    path('<int:pk>/delete/', EventDeleteView.as_view(), name='event-delete'),
]
