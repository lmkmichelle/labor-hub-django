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
from django.views.generic import TemplateView

from .views import ProfileView, EditProfileView, CustomLoginView, ApplicationSubmittedView, ResearcherApplicationView, \
    StudentApplicationView, SettingsView, digest_unsubscribe, AdviseeApplicationsView, advisee_approve, advisee_reject

urlpatterns = [
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/<int:pk>/', ProfileView.as_view(), name='profile'),
    path('profile/edit/', EditProfileView.as_view(), name='edit_profile'),
    path('settings/', SettingsView.as_view(), name='settings'),
    path('accounts/advisees/', AdviseeApplicationsView.as_view(), name='advisee_applications'),
    path('accounts/advisees/<int:pk>/approve/', advisee_approve, name='advisee_approve'),
    path('accounts/advisees/<int:pk>/reject/', advisee_reject, name='advisee_reject'),
    path('accounts/digest/unsubscribe/<str:token>/', digest_unsubscribe, name='digest_unsubscribe'),
    path('accounts/membership/', TemplateView.as_view(template_name='accounts/apply_landing.html'), name='membership'),
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
