from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import CustomUser, ResearchPaper, UserApplication


def make_active_user(email="user@example.com", password="pass12345",
                     role=CustomUser.Role.RESEARCHER):
    return CustomUser.objects.create_user(
        email=email, password=password, first_name="First", last_name="Last",
        role=role, is_active=True,
    )


def make_image_file(name="avatar.png"):
    buffer = BytesIO()
    Image.new("RGB", (400, 400), "blue").save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/png")


def application_post_data(**overrides):
    data = {
        "email": "applicant@example.com",
        "first_name": "Ann",
        "last_name": "Applicant",
        "education": "Cornell",
        "country_code": "US",
        "motivation": "Please let me in.",
        "password1": "pass12345",
        "password2": "pass12345",
    }
    data.update(overrides)
    return data


class ApplicationViewTests(TestCase):
    def test_apply_researcher_get(self):
        response = self.client.get(reverse("apply_researcher"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/apply.html")
        self.assertEqual(response.context["application_type"], "Researcher")

    def test_apply_student_get(self):
        response = self.client.get(reverse("apply_student"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["application_type"], "Student")

    def test_apply_researcher_post_creates_application(self):
        response = self.client.post(
            reverse("apply_researcher"), application_post_data())
        self.assertRedirects(
            response, reverse("application_submitted"),
            fetch_redirect_response=False)
        application = UserApplication.objects.get(email="applicant@example.com")
        self.assertEqual(application.role, CustomUser.Role.RESEARCHER)
        self.assertEqual(application.status, UserApplication.Status.PENDING)

    def test_apply_researcher_post_with_paper_creates_research_paper(self):
        data = application_post_data()
        data["research_papers"] = SimpleUploadedFile(
            "paper.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        response = self.client.post(reverse("apply_researcher"), data)
        self.assertEqual(response.status_code, 302)
        application = UserApplication.objects.get(email="applicant@example.com")
        self.assertEqual(
            ResearchPaper.objects.filter(application=application).count(), 1)


class LoginViewTests(TestCase):
    def test_login_get(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_login_post_valid_authenticates(self):
        make_active_user(email="login@example.com", password="pass12345")
        response = self.client.post(
            reverse("login"),
            {"username": "login@example.com", "password": "pass12345"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)


class ProfileViewTests(TestCase):
    def test_profile_by_pk_renders(self):
        user = make_active_user()
        response = self.client.get(reverse("profile", kwargs={"pk": user.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile.html")

    def test_profile_unknown_pk_returns_404(self):
        response = self.client.get(reverse("profile", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, 404)

    def test_profile_no_pk_unauthenticated_redirects_to_login(self):
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/login/")

    def test_profile_no_pk_authenticated_shows_own(self):
        user = make_active_user()
        self.client.force_login(user)
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile_user"], user)


class EditProfileViewTests(TestCase):
    def test_get_requires_login(self):
        response = self.client.get(reverse("edit_profile"))
        self.assertEqual(response.status_code, 302)

    def test_get_authenticated_renders(self):
        user = make_active_user()
        self.client.force_login(user)
        response = self.client.get(reverse("edit_profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/edit_profile.html")

    def test_post_updates_profile_and_crops_avatar(self):
        user = make_active_user()
        self.client.force_login(user)
        response = self.client.post(reverse("edit_profile"), {
            "email": user.email,
            "position": "Professor",
            "country_code": "US",
            "education": "Cornell",
            "website": "https://example.com",
            "biography": "A short biography.",
            "research_interests_input": '[{"value":"Economics"}]',
            "avatar": make_image_file(),
        })
        self.assertRedirects(response, reverse("profile"))
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.position, "Professor")
        self.assertEqual(user.profile.research_interests, [{"value": "Economics"}])
        self.assertTrue(user.profile.avatar)
