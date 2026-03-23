from django.urls import path

from .views import JobDetailView, JobsListView

urlpatterns = [
	path('', JobsListView.as_view(), name='jobs-list'),
	path('<int:pk>/', JobDetailView.as_view(), name='job-detail'),
]
