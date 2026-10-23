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


class AdminCvLinkColumnTests(TestCase):
    def setUp(self):
        self.client.force_login(
            CustomUser.objects.create_superuser(email="a@example.com", password="pass12345"))

    def _apply(self, email, **extra):
        return UserApplication.objects.create(
            email=email, first_name="C", last_name="V", role=CustomUser.Role.RESEARCHER,
            password="x", **extra)

    def test_changelist_links_the_cv_url(self):
        self._apply("cv@example.com", cv_url="https://example.com/jane-cv.pdf")
        page = self.client.get(reverse("admin:accounts_userapplication_changelist"))
        self.assertContains(page, 'href="https://example.com/jane-cv.pdf"')
        self.assertContains(page, "CV link")

    def test_no_cv_url_shows_a_dash(self):
        self._apply("nocv@example.com")
        page = self.client.get(reverse("admin:accounts_userapplication_changelist"))
        self.assertNotContains(page, "CV link")

    def test_change_page_links_it_too(self):
        app = self._apply("cv2@example.com", cv_url="https://example.com/cv")
        page = self.client.get(reverse("admin:accounts_userapplication_change", args=[app.pk]))
        self.assertContains(page, 'href="https://example.com/cv"')
