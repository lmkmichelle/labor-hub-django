"""Transactional emails for the accounts app.

The "your application was approved" notification sent when an admin approves a
:class:`~accounts.models.UserApplication`, plus the two submission-time
notifications: one to every staff member, and one to the advisor a student
named on their application.
"""
from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
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
    body = (
        f"A new {role_label} application is awaiting review.\n\n"
        f"Name: {application.first_name} {application.last_name}\n"
        f"Email: {application.email}\n"
        f"Role: {role_label}\n"
        f"Submitted: {application.applied_at:%Y-%m-%d %H:%M}\n\n"
        f"Review it: {review_url}\n"
    )
    EmailMessage(
        subject=f"[Labor Hub] New {role_label} application: "
        f"{application.first_name} {application.last_name}",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
        reply_to=[application.email],
    ).send(fail_silently=fail_silently)


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
        f"A student listed you as their advisor on Labor Hub: "
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
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=fail_silently)
