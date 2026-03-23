from django.urls import path

from .views import JobsListView

urlpatterns = [
	path('', JobsListView.as_view(), name='jobs-list'),
]
