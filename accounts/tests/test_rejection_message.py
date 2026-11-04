from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import DEFAULT_REJECTION_MESSAGE, CustomUser, UserApplication


class RejectionMessageTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_superuser(
            email="admin@example.com", password="pw12345", first_name="Ad", last_name="Min")
        self.client.force_login(self.admin_user)

    def _application(self, role=CustomUser.Role.RESEARCHER, **kwargs):
        return UserApplication.objects.create(
            email="s@example.com", first_name="S", last_name="T", role=role, password="x", **kwargs)

    def test_deny_page_shows_the_message_and_sends_the_edited_text(self):
        application = self._application()
        url = reverse("admin:reject_application", args=[application.pk])
        page = self.client.get(url)
        self.assertContains(page, "not able to accept your application")
        self.assertContains(page, "Ask them to apply as a student")
        application.refresh_from_db()
        self.assertEqual(application.status, "pending")        # a GET denies nothing
        self.assertContains(self.client.get(url + "?preset=student_route"), reverse("apply_student"))

        self.client.post(url, {"message": "Please apply as a student & name your advisor."})
        application.refresh_from_db()
        self.assertEqual(application.status, "rejected")
        self.assertEqual(application.rejection_message, "Please apply as a student & name your advisor.")
        self.assertIn("apply as a student & name", mail.outbox[-1].body)

    def test_student_route_preset_only_for_scholar_applications(self):
        application = self._application(role=CustomUser.Role.STUDENT)
        page = self.client.get(reverse("admin:reject_application", args=[application.pk]))
        self.assertNotContains(page, "Ask them to apply as a student")

    def test_deny_refuses_an_empty_message_and_reviewed_applications(self):
        application = self._application()
        url = reverse("admin:reject_application", args=[application.pk])
        self.assertContains(self.client.post(url, {"message": " "}), "Write a message")
        application.refresh_from_db()
        self.assertEqual(application.status, "pending")
        application.reject(self.admin_user)
        self.assertEqual(self.client.post(url, {"message": "x"}).status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.rejection_message, DEFAULT_REJECTION_MESSAGE)

    def test_application_page_shows_the_message_that_was_sent(self):
        application = self._application()
        application.reject(self.admin_user, "A custom note")
        page = self.client.get(reverse("admin:accounts_userapplication_change", args=[application.pk]))
        self.assertContains(page, "A custom note")
