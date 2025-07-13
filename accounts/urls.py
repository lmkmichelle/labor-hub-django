from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from . import views
from .views import SignUpView, ProfileView, EditProfileView, CustomLoginView

urlpatterns = [
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/<int:pk>', ProfileView.as_view(), name='profile'),
    path('profile/edit/', EditProfileView.as_view(), name='edit_profile'),
    path('accounts/signup/', SignUpView.as_view(), name='signup'),
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    path('api/accounts/search/', views.search_accounts, name='search_accounts'),
    path('api/country-users/', views.country_users, name='country_users'),
]
