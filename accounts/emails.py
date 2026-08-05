"""Transactional emails for the accounts app.

Currently just the "your application was approved" notification, sent when an
admin approves a :class:`~accounts.models.UserApplication` and the member's
account goes live.
"""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse


def _absolute_url(path):
    """Prefix a root-relative path with the configured public site URL."""
    return "{}{}".format(settings.SITE_URL.rstrip("/"), path)


def send_application_approved_email(user, fail_silently=True):
    """Email an approved applicant that their account is active.

    Sends a plain-text + HTML message pointing at the sign-in page. Transport
    failures are swallowed by default so a mail outage cannot undo an approval
    that has already created the user account.
    """
    context = {
        "user": user,
        "login_url": _absolute_url(reverse("login")),
        "site_url": settings.SITE_URL.rstrip("/"),
    }
    subject = "Your Labor Hub application has been approved"
    text_body = render_to_string("emails/application_approved.txt", context)
    html_body = render_to_string("emails/application_approved.html", context)

    message = EmailMultiAlternatives(
        subject,
        text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=fail_silently)
