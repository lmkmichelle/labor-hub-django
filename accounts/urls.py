from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import ProfileView, EditProfileView, CustomLoginView, ApplicationSubmittedView, ResearcherApplicationView, \
    StudentApplicationView

urlpatterns = [
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/<int:pk>', ProfileView.as_view(), name='profile'),
    path('profile/edit/', EditProfileView.as_view(), name='edit_profile'),
    path('accounts/apply/researcher/', ResearcherApplicationView.as_view(), name='apply_researcher'),
    path('accounts/apply/student/', StudentApplicationView.as_view(), name='apply_student'),
    path('accounts/application-submitted', ApplicationSubmittedView.as_view(), name='application_submitted'),
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
]
