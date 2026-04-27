from django.urls import path

from .views import JobCreateView, JobDetailView, JobsListView

urlpatterns = [
	path('', JobsListView.as_view(), name='jobs-list'),
	path('create/', JobCreateView.as_view(), name='job-create'),
	path('<int:pk>/', JobDetailView.as_view(), name='job-detail'),
]
