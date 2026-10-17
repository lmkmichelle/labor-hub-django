from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser, UserApplication


class AdminAdvisorColumnTests(TestCase):
    def test_pending_student_shows_advisor_and_awaiting(self):
        admin = CustomUser.objects.create_superuser(email="a@example.com", password="pass12345")
        advisor = CustomUser.objects.create_user(
            email="adv@example.com", password="x", first_name="Ada", last_name="Visor",
            role=CustomUser.Role.RESEARCHER, is_active=True)
        UserApplication.objects.create(
            email="s@example.com", first_name="S", last_name="T",
            role=CustomUser.Role.STUDENT, advisor=advisor, password="x")
        self.client.force_login(admin)
        response = self.client.get(reverse("admin:accounts_userapplication_changelist"))
        self.assertContains(response, "Ada Visor")
        self.assertContains(response, "Awaiting advisor")
