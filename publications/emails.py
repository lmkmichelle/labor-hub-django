"""Transactional email for the job-market-paper advisor acknowledgement.

When a job market paper is submitted with a named advisor, the advisor is asked
to confirm or decline on the site (mirrors accounts.emails.send_advisor_review_email).
"""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse


def _absolute_url(path):
    return "{}{}".format(settings.SITE_URL.rstrip("/"), path)


def send_paper_advisor_ack_email(publication, fail_silently=True):
    """Ask the named advisor to acknowledge a job market paper.

    No-op unless the paper is flagged job-market and has an advisor with an
    email. Links to the on-site "Advised papers" page (login required), never
    the admin.
    """
    advisor = publication.jm_advisor
    if not publication.is_job_market or advisor is None or not advisor.email:
        return

    submitter = publication.submitted_by
    context = {
        "advisor": advisor,
        "publication": publication,
        "submitter": submitter,
        "review_url": _absolute_url(reverse("advised_papers")),
        "site_url": settings.SITE_URL.rstrip("/"),
    }
    subject = (
        f"You were listed as the advisor on a job market paper: {publication.title}"
    )
    text_body = render_to_string("emails/paper_advisor_ack.txt", context)
    html_body = render_to_string("emails/paper_advisor_ack.html", context)

    message = EmailMultiAlternatives(
        subject,
        text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[advisor.email],
        reply_to=[submitter.email] if submitter and submitter.email else None,
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=fail_silently)
