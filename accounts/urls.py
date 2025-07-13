from django.urls import path
from . import views
from .views import SignUpView, ProfileView, EditProfileView

urlpatterns = [
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/<int:pk>', ProfileView.as_view(), name='profile'),
    path('profile/edit/', EditProfileView.as_view(), name='edit_profile'),
    path('accounts/signup/', SignUpView.as_view(), name='signup'),
    path('api/accounts/search/', views.search_accounts, name='search_accounts')
]
