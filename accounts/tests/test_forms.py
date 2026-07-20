from django.contrib.auth.hashers import check_password
from django.test import TestCase

from accounts.forms import (
    ResearcherApplicationForm,
    StudentApplicationForm,
    UpdateProfileForm,
)
from accounts.models import CustomUser, UserApplication


def base_application_data(**overrides):
    data = {
        "email": "applicant@example.com",
        "first_name": "Ann",
        "last_name": "Applicant",
        "education": "Cornell",
        "country_code": "US",
        "motivation": "I want to join.",
        "password1": "pass12345",
        "password2": "pass12345",
    }
    data.update(overrides)
    return data


def make_researcher(email="advisor@example.com"):
    return CustomUser.objects.create_user(
        email=email, password="pass12345", first_name="Adam", last_name="Advisor",
        role=CustomUser.Role.RESEARCHER, is_active=True,
    )


class ResearcherApplicationFormTests(TestCase):
    def test_valid_form_saves_hashed_password(self):
        form = ResearcherApplicationForm(data=base_application_data())
        self.assertTrue(form.is_valid(), form.errors)
        application = form.save()
        self.assertIsNotNone(application.pk)
        self.assertEqual(application.role, CustomUser.Role.RESEARCHER)
        self.assertEqual(application.status, UserApplication.Status.PENDING)
        self.assertNotEqual(application.password, "pass12345")
        self.assertTrue(check_password("pass12345", application.password))

    def test_password_mismatch_is_invalid(self):
        form = ResearcherApplicationForm(
            data=base_application_data(password2="different"))
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_duplicate_user_email_is_invalid(self):
        make_researcher(email="applicant@example.com")
        form = ResearcherApplicationForm(data=base_application_data())
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_duplicate_pending_application_email_is_invalid(self):
        UserApplication.objects.create(
            email="applicant@example.com", first_name="X", last_name="Y",
            position="p", education="e", password="x",
            status=UserApplication.Status.PENDING,
        )
        form = ResearcherApplicationForm(data=base_application_data())
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)


class StudentApplicationFormTests(TestCase):
    def test_valid_form_sets_role_student(self):
        advisor = make_researcher()
        form = StudentApplicationForm(
            data=base_application_data(email="student@example.com",
                                       advisor=advisor.pk))
        self.assertTrue(form.is_valid(), form.errors)
        application = form.save()
        self.assertEqual(application.role, CustomUser.Role.STUDENT)

    def test_missing_advisor_is_invalid(self):
        form = StudentApplicationForm(
            data=base_application_data(email="student@example.com"))
        self.assertFalse(form.is_valid())
        self.assertIn("advisor", form.errors)

    def test_advisor_label_uses_position(self):
        advisor = make_researcher()
        advisor.profile.position = "Professor"
        advisor.profile.save()
        field = StudentApplicationForm().fields["advisor"]
        self.assertEqual(field.label_from_instance(advisor),
                         "Adam Advisor - Professor")

    def test_advisor_label_falls_back_to_researcher(self):
        advisor = make_researcher()
        field = StudentApplicationForm().fields["advisor"]
        self.assertEqual(field.label_from_instance(advisor),
                         "Adam Advisor - Researcher")


class UpdateProfileFormTests(TestCase):
    def test_research_interests_prefilled_as_tagify_json(self):
        user = make_researcher(email="user@example.com")
        user.profile.research_interests = ["Economics", "Policy"]
        user.profile.save()
        form = UpdateProfileForm(instance=user.profile)
        widget_value = form.fields["research_interests_input"].widget.attrs["value"]
        self.assertIn("Economics", widget_value)
        self.assertIn("Policy", widget_value)
