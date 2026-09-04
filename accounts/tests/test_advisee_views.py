from django.contrib.auth.hashers import make_password
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import CustomUser, UserApplication


def make_researcher(email="advisor@example.com"):
    return CustomUser.objects.create_user(
        email=email, password="pass12345", first_name="Adam", last_name="Advisor",
        role=CustomUser.Role.RESEARCHER, is_active=True,
    )


def make_student_application(advisor, email="student@example.com",
                             status=UserApplication.Status.PENDING):
    return UserApplication.objects.create(
        email=email, first_name="Sam", last_name="Student",
        role=CustomUser.Role.STUDENT, department="Econ",
        password=make_password("pass12345"), country_code="US",
        advisor=advisor, status=status,
    )


class AdviseeListViewTests(TestCase):
    def test_login_required(self):
        response = self.client.get(reverse("advisee_applications"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_lists_only_own_pending_and_reviewed_advisees(self):
        advisor = make_researcher()
        other = make_researcher(email="other@example.com")
        mine = make_student_application(advisor, email="mine@example.com")
        make_student_application(other, email="theirs@example.com")

        self.client.force_login(advisor)
        response = self.client.get(reverse("advisee_applications"))

        self.assertEqual(response.status_code, 200)
        applications = list(response.context["applications"])
        self.assertEqual(applications, [mine])

    def test_researcher_with_no_advisees_sees_empty_state(self):
        advisor = make_researcher()
        self.client.force_login(advisor)
        response = self.client.get(reverse("advisee_applications"))
        self.assertEqual(list(response.context["applications"]), [])


class AdviseeApproveTests(TestCase):
    def test_approve_creates_account_with_advisor_linked(self):
        advisor = make_researcher()
        app = make_student_application(advisor)

        self.client.force_login(advisor)
        response = self.client.post(
            reverse("advisee_approve", args=[app.pk]))

        self.assertRedirects(response, reverse("advisee_applications"))
        app.refresh_from_db()
        self.assertEqual(app.status, UserApplication.Status.APPROVED)
        user = CustomUser.objects.get(email=app.email)
        self.assertTrue(user.is_student())
        self.assertEqual(user.advisor, advisor)

    def test_other_researcher_gets_404(self):
        advisor = make_researcher()
        intruder = make_researcher(email="intruder@example.com")
        app = make_student_application(advisor)

        self.client.force_login(intruder)
        response = self.client.post(
            reverse("advisee_approve", args=[app.pk]))

        self.assertEqual(response.status_code, 404)
        app.refresh_from_db()
        self.assertEqual(app.status, UserApplication.Status.PENDING)

    def test_get_does_not_mutate(self):
        advisor = make_researcher()
        app = make_student_application(advisor)

        self.client.force_login(advisor)
        response = self.client.get(
            reverse("advisee_approve", args=[app.pk]))

        self.assertEqual(response.status_code, 405)
        app.refresh_from_db()
        self.assertEqual(app.status, UserApplication.Status.PENDING)
        self.assertFalse(CustomUser.objects.filter(email=app.email).exists())

    def test_already_reviewed_application_is_left_alone(self):
        advisor = make_researcher()
        app = make_student_application(
            advisor, status=UserApplication.Status.REJECTED)

        self.client.force_login(advisor)
        response = self.client.post(
            reverse("advisee_approve", args=[app.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, UserApplication.Status.REJECTED)


class AdviseeRejectTests(TestCase):
    def test_reject_sets_status(self):
        advisor = make_researcher()
        app = make_student_application(advisor)

        self.client.force_login(advisor)
        response = self.client.post(
            reverse("advisee_reject", args=[app.pk]))

        self.assertRedirects(response, reverse("advisee_applications"))
        app.refresh_from_db()
        self.assertEqual(app.status, UserApplication.Status.REJECTED)
        self.assertFalse(CustomUser.objects.filter(email=app.email).exists())


class AdviseeNavAndCountTests(TestCase):
    def test_context_processor_counts_only_pending_own_students(self):
        advisor = make_researcher()
        make_student_application(advisor, email="p1@example.com")
        make_student_application(advisor, email="p2@example.com")
        make_student_application(
            advisor, email="done@example.com",
            status=UserApplication.Status.APPROVED)

        self.client.force_login(advisor)
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.context["pending_advisee_count"], 2)

    def test_count_is_zero_for_anonymous(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["pending_advisee_count"], 0)


@override_settings(SITE_URL="http://testserver")
class ApplicationNotificationEmailTests(TestCase):
    def test_staff_notified_on_submission(self):
        CustomUser.objects.create_user(
            email="staff@example.com", password="x", first_name="S",
            last_name="Taff", role=CustomUser.Role.ADMIN, is_active=True,
            is_staff=True,
        )
        data = {
            "email": "newapplicant@example.com", "first_name": "New",
            "last_name": "Applicant", "department": "Econ", "country_code": "US",
            "motivation": "hi", "password1": "pass12345", "password2": "pass12345",
        }
        self.client.post(reverse("apply_researcher"), data)

        staff_mails = [m for m in mail.outbox if "staff@example.com" in m.to]
        self.assertEqual(len(staff_mails), 1)
        self.assertIn("application", staff_mails[0].subject.lower())

    def test_advisor_notified_on_student_submission(self):
        advisor = make_researcher()
        data = {
            "email": "newstudent@example.com", "first_name": "New",
            "last_name": "Student", "department": "Econ", "country_code": "US",
            "motivation": "hi", "password1": "pass12345", "password2": "pass12345",
            "advisor": advisor.pk,
        }
        self.client.post(reverse("apply_student"), data)

        advisor_mails = [m for m in mail.outbox if advisor.email in m.to]
        self.assertEqual(len(advisor_mails), 1)
        self.assertIn("advisor", advisor_mails[0].subject.lower())
