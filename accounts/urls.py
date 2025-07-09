from django.urls import path
from . import views
from .views import SignUpView

urlpatterns = [
    path('profile/', views.profile, name='profile'),
    path('accounts/signup/', SignUpView.as_view(), name='signup'),
    path('api/accounts/search/', views.search_accounts, name='search_accounts')
]
