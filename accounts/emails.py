"""Transactional emails for the accounts app.

The "your application was approved"/"was not accepted" notifications sent when
an admin decides a :class:`~accounts.models.UserApplication`, plus the two
submission-time notifications: one to every staff member, and one to the
advisor a student named on their application.
"""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from core.email import attach_logo, cm_headers, default_reply_to


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
        reply_to=default_reply_to(),
        headers=cm_headers("Application decision"),
    )
    message.attach_alternative(html_body, "text/html")
    attach_logo(message)
    message.send(fail_silently=fail_silently)


def send_application_rejected_email(application, fail_silently=True):
    """Email an applicant that their application was not accepted.

    Mirrors ``send_application_approved_email``: plain-text + HTML, no reason
    given (none is currently recorded), and fails silently so a mail outage
    can't disrupt the review flow -- the decision is already saved.
    """
    context = {
        "application": application,
        "site_url": settings.SITE_URL.rstrip("/"),
    }
    subject = "An update on your Labor Hub application"
    text_body = render_to_string("emails/application_rejected.txt", context)
    html_body = render_to_string("emails/application_rejected.html", context)

    message = EmailMultiAlternatives(
        subject,
        text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[application.email],
        reply_to=default_reply_to(),
        headers=cm_headers("Application decision"),
    )
    message.attach_alternative(html_body, "text/html")
    attach_logo(message)
    message.send(fail_silently=fail_silently)


def send_application_submitted_email(application, fail_silently=True):
    """Notify every active staff member that a new application needs review.

    Modeled on ``core.views._send_contact_notification``: sent from
    ``DEFAULT_FROM_EMAIL`` with ``Reply-To`` set to the applicant, and failing
    silently so a mail outage can't 500 the applicant whose row is already saved.
    """
    from accounts.models import CustomUser

    recipients = list(
        CustomUser.objects.filter(is_staff=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not recipients:
        return

    role_label = application.get_role_display()
    review_url = _absolute_url(
        reverse("admin:accounts_userapplication_change", args=[application.pk])
    )
    context = {
        "application": application,
        "role_label": role_label,
        "review_url": review_url,
        "site_url": settings.SITE_URL.rstrip("/"),
    }
    text_body = render_to_string("emails/application_submitted.txt", context)
    html_body = render_to_string("emails/application_submitted.html", context)

    message = EmailMultiAlternatives(
        subject=f"[Action Required] New {role_label} application: "
        f"{application.first_name} {application.last_name}",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
        reply_to=[application.email],
        headers=cm_headers("Staff alerts"),
    )
    message.attach_alternative(html_body, "text/html")
    attach_logo(message)
    message.send(fail_silently=fail_silently)


def send_advisor_review_email(application, fail_silently=True):
    """Tell the advisor a student named that they can review the application.

    Links to the on-site advisee review page, never the admin. No-op unless the
    application is a student application with an advisor attached.
    """
    from accounts.models import CustomUser

    advisor = application.advisor
    if application.role != CustomUser.Role.STUDENT or advisor is None:
        return
    if not advisor.email:
        return

    context = {
        "advisor": advisor,
        "application": application,
        "review_url": _absolute_url(reverse("advisee_applications")),
        "site_url": settings.SITE_URL.rstrip("/"),
    }
    subject = (
        f"[Action Required] A student listed you as their advisor: "
        f"{application.first_name} {application.last_name}"
    )
    text_body = render_to_string("emails/advisor_review.txt", context)
    html_body = render_to_string("emails/advisor_review.html", context)

    message = EmailMultiAlternatives(
        subject,
        text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[advisor.email],
        reply_to=[application.email],
        headers=cm_headers("Advisor requests"),
    )
    message.attach_alternative(html_body, "text/html")
    attach_logo(message)
    message.send(fail_silently=fail_silently)
