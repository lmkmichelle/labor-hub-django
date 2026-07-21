from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import CustomUser, Profile, ResearchPaper, UserApplication

User = get_user_model()


def make_user(email="researcher@example.com", password="pass12345",
              role=CustomUser.Role.RESEARCHER, is_active=True, **extra):
    return CustomUser.objects.create_user(
        email=email,
        password=password,
        first_name=extra.pop("first_name", "First"),
        last_name=extra.pop("last_name", "Last"),
        role=role,
        is_active=is_active,
        **extra,
    )


class CustomUserManagerTests(TestCase):
    def test_create_user_defaults(self):
        user = make_user(is_active=False)
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("pass12345"))
        self.assertEqual(user.username, user.email)

    def test_create_user_requires_email(self):
        with self.assertRaises(ValueError):
            CustomUser.objects.create_user(email="", password="pass12345")

    def test_create_user_normalizes_email_domain(self):
        user = CustomUser.objects.create_user(
            email="Person@EXAMPLE.COM", password="pass12345",
            first_name="A", last_name="B",
        )
        self.assertEqual(user.email, "Person@example.com")

    def test_create_superuser_defaults(self):
        admin = CustomUser.objects.create_superuser(
            email="admin@example.com", password="pass12345",
            first_name="A", last_name="B",
        )
        self.assertTrue(admin.is_active)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_create_superuser_requires_is_staff(self):
        with self.assertRaises(ValueError):
            CustomUser.objects.create_superuser(
                email="a@example.com", password="pass12345",
                first_name="A", last_name="B", is_staff=False,
            )

    def test_create_superuser_requires_is_superuser(self):
        with self.assertRaises(ValueError):
            CustomUser.objects.create_superuser(
                email="a@example.com", password="pass12345",
                first_name="A", last_name="B", is_superuser=False,
            )

    def test_create_superuser_requires_is_active(self):
        with self.assertRaises(ValueError):
            CustomUser.objects.create_superuser(
                email="a@example.com", password="pass12345",
                first_name="A", last_name="B", is_active=False,
            )


class CustomUserModelTests(TestCase):
    def test_str_includes_email_and_role(self):
        user = make_user()
        self.assertEqual(str(user), f"{user.email} (Researcher)")

    def test_username_defaults_to_email(self):
        user = make_user()
        self.assertEqual(user.username, "researcher@example.com")

    def test_save_clears_advisor_for_non_student(self):
        advisor = make_user(email="advisor@example.com")
        user = make_user(email="person@example.com",
                         role=CustomUser.Role.RESEARCHER, advisor=advisor)
        user.refresh_from_db()
        self.assertIsNone(user.advisor)

    def test_save_keeps_advisor_for_student(self):
        advisor = make_user(email="advisor@example.com")
        student = make_user(email="student@example.com",
                            role=CustomUser.Role.STUDENT, advisor=advisor)
        student.refresh_from_db()
        self.assertEqual(student.advisor, advisor)

    def test_role_helpers(self):
        student = make_user(email="s@example.com", role=CustomUser.Role.STUDENT)
        researcher = make_user(email="r@example.com", role=CustomUser.Role.RESEARCHER)
        self.assertTrue(student.is_student())
        self.assertFalse(student.is_researcher())
        self.assertTrue(researcher.is_researcher())
        self.assertFalse(researcher.is_student())


class ProfileModelTests(TestCase):
    def test_str_returns_email(self):
        user = make_user()
        self.assertEqual(str(user.profile), user.email)

    def test_research_interest_list_normalizes_dicts_and_strings(self):
        user = make_user()
        user.profile.research_interests = [
            {"value": "Economics"}, "Policy", {"value": " "}, "", None,
        ]
        user.profile.save()
        self.assertEqual(
            user.profile.research_interest_list(), ["Economics", "Policy"]
        )


def make_application(email="applicant@example.com", role=CustomUser.Role.RESEARCHER,
                     status=UserApplication.Status.PENDING):
    return UserApplication.objects.create(
        email=email,
        first_name="Ann",
        last_name="Applicant",
        role=role,
        position="Fellow",
        education="Cornell",
        password=make_password("pass12345"),
        country_code="US",
        status=status,
    )


class UserApplicationTests(TestCase):
    def test_approve_creates_active_user_and_copies_profile(self):
        admin = make_user(email="admin@example.com", role=CustomUser.Role.ADMIN)
        app = make_application()

        user = app.approve(admin_user=admin)

        self.assertTrue(user.is_active)
        self.assertEqual(user.role, CustomUser.Role.RESEARCHER)
        self.assertEqual(user.profile.position, "Fellow")
        self.assertEqual(user.profile.education, "Cornell")
        self.assertEqual(user.profile.country_code, "US")

        app.refresh_from_db()
        self.assertEqual(app.status, UserApplication.Status.APPROVED)
        self.assertIsNotNone(app.reviewed_at)
        self.assertEqual(app.reviewed_by, admin)

    def test_approve_non_pending_raises(self):
        app = make_application(status=UserApplication.Status.APPROVED)
        with self.assertRaises(ValueError):
            app.approve()

    def test_approve_existing_email_raises(self):
        make_user(email="dup@example.com")
        app = make_application(email="dup@example.com")
        with self.assertRaises(ValueError):
            app.approve()

    def test_approve_student_sets_advisor(self):
        advisor = make_user(email="advisor@example.com")
        app = make_application(email="student@example.com",
                               role=CustomUser.Role.STUDENT)
        user = app.approve(advisor=advisor)
        self.assertTrue(user.is_student())
        self.assertEqual(user.advisor, advisor)

    def test_approve_researcher_ignores_advisor(self):
        advisor = make_user(email="advisor@example.com")
        app = make_application(email="researcher2@example.com",
                               role=CustomUser.Role.RESEARCHER)
        user = app.approve(advisor=advisor)
        self.assertIsNone(user.advisor)

    def test_reject_sets_status(self):
        admin = make_user(email="admin@example.com", role=CustomUser.Role.ADMIN)
        app = make_application()
        app.reject(admin)
        app.refresh_from_db()
        self.assertEqual(app.status, UserApplication.Status.REJECTED)
        self.assertEqual(app.reviewed_by, admin)
        self.assertIsNotNone(app.reviewed_at)

    def test_reject_non_pending_raises(self):
        admin = make_user(email="admin@example.com", role=CustomUser.Role.ADMIN)
        app = make_application(status=UserApplication.Status.REJECTED)
        with self.assertRaises(ValueError):
            app.reject(admin)


class ResearchPaperConstraintTests(TestCase):
    def test_pdf_paper_is_allowed(self):
        app = make_application()
        paper = ResearchPaper.objects.create(
            application=app, paper="research_papers/study.pdf")
        self.assertTrue(paper.paper.name.endswith(".pdf"))

    def test_non_pdf_paper_is_rejected(self):
        app = make_application()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ResearchPaper.objects.create(
                    application=app, paper="research_papers/study.txt")
