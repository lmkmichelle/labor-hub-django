from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from . import views
from .views import ProfileView, EditProfileView, CustomLoginView, ApplicationSubmittedView, ApplyView

urlpatterns = [
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/<int:pk>', ProfileView.as_view(), name='profile'),
    path('profile/edit/', EditProfileView.as_view(), name='edit_profile'),
    path('accounts/apply/', ApplyView.as_view(), name='apply'),
    path('accounts/application-submitted', ApplicationSubmittedView.as_view(), name='application_submitted'),
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
]
