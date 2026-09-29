"""Password reset email -- routed through core.email like every other
transactional send (CM grouping headers, reply-to, inline logo), via
accounts.forms.LaborHubPasswordResetForm (see accounts/urls.py)."""
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import CustomUser
from core.tests.email_assertions import assert_has_html_alternative_with_logo


def make_user(email="reset@example.com"):
    return CustomUser.objects.create_user(
        email=email, password="pass12345",
        first_name="Reset", last_name="Me", is_active=True,
    )


@override_settings(REPLY_TO_EMAIL="laborhub@cornell.edu")
class PasswordResetEmailTests(TestCase):
    def test_reset_email_is_html_with_the_inline_logo(self):
        user = make_user()
        self.client.post(reverse("password_reset"), {"email": user.email})

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [user.email])
        self.assertEqual(message.subject, "Reset your Labor Hub password")
        html_body = assert_has_html_alternative_with_logo(self, message)
        self.assertIn("Reset my password", html_body)

    def test_reset_email_uses_cm_headers_and_reply_to(self):
        user = make_user()
        self.client.post(reverse("password_reset"), {"email": user.email})

        message = mail.outbox[0]
        self.assertEqual(
            message.extra_headers.get("X-Cmail-GroupName"),
            "LaborHub")
        self.assertEqual(message.reply_to, ["laborhub@cornell.edu"])

    def test_unknown_email_sends_nothing(self):
        self.client.post(
            reverse("password_reset"), {"email": "nobody@example.com"})
        self.assertEqual(len(mail.outbox), 0)
