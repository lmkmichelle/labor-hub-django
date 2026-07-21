from django.contrib.auth.views import (
    LogoutView, 
    PasswordChangeView, 
    PasswordChangeDoneView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView
)
from django.urls import path

from .views import ProfileView, EditProfileView, CustomLoginView, ApplicationSubmittedView, ResearcherApplicationView, \
    StudentApplicationView

urlpatterns = [
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/<int:pk>/', ProfileView.as_view(), name='profile'),
    path('profile/edit/', EditProfileView.as_view(), name='edit_profile'),
    path('accounts/apply/researcher/', ResearcherApplicationView.as_view(), name='apply_researcher'),
    path('accounts/apply/student/', StudentApplicationView.as_view(), name='apply_student'),
    path('accounts/application-submitted', ApplicationSubmittedView.as_view(), name='application_submitted'),
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    
    # Password management URLs
    path('accounts/password-change/', PasswordChangeView.as_view(template_name='registration/password_change.html'), name='password_change'),
    path('accounts/password-change/done/', PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'), name='password_change_done'),
    path('accounts/password-reset/', PasswordResetView.as_view(
        template_name='registration/password_reset.html',
        email_template_name='registration/password_reset_email.txt',
        subject_template_name='registration/password_reset_subject.txt',
        html_email_template_name='registration/password_reset_email.html',
    ), name='password_reset'),
    path('accounts/password-reset/done/', PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('accounts/password-reset-confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('accounts/password-reset-complete/', PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
]
