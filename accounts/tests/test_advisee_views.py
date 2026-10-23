from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.hashers import make_password
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import CustomUser, UserApplication
from core.tests.email_assertions import assert_has_html_alternative_with_logo


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


@override_settings(SITE_URL="http://testserver", ADMIN_NOTIFY_EMAIL="ega@example.com")
class ApplicationNotificationEmailTests(TestCase):
    def _staff(self):
        return CustomUser.objects.create_user(
            email="staff@example.com", password="x", first_name="S",
            last_name="Taff", role=CustomUser.Role.ADMIN, is_active=True,
            is_staff=True,
        )

    def _student_data(self, **extra):
        data = {
            "email": "newstudent@example.com", "first_name": "New",
            "last_name": "Student", "department": "Econ", "country_code": "US",
            "motivation": "hi", "password1": "pass12345", "password2": "pass12345",
        }
        data.update(extra)
        return data

    def test_shared_inbox_notified_on_scholar_submission_not_each_staff_user(self):
        self._staff()
        data = {
            "email": "newapplicant@example.com", "first_name": "New",
            "last_name": "Applicant", "department": "Econ", "country_code": "US",
            "motivation": "hi", "password1": "pass12345", "password2": "pass12345",
            "research_paper_1": SimpleUploadedFile("a.pdf", b"%PDF-1.4 a", content_type="application/pdf"),
            "research_paper_2": SimpleUploadedFile("b.pdf", b"%PDF-1.4 b", content_type="application/pdf"),
        }
        self.client.post(reverse("apply_researcher"), data)

        self.assertFalse([m for m in mail.outbox if "staff@example.com" in m.to])
        ega_mails = [m for m in mail.outbox if m.to == ["ega@example.com"]]
        self.assertEqual(len(ega_mails), 1)
        self.assertIn("application", ega_mails[0].subject.lower())
        self.assertTrue(ega_mails[0].subject.startswith("[Action Required]"))
        self.assertEqual(ega_mails[0].reply_to, ["newapplicant@example.com"])
        self.assertEqual(
            ega_mails[0].extra_headers.get("X-Cmail-GroupName"),
            "LaborHub")
        # Regression: this notification used to be plain-text only.
        assert_has_html_alternative_with_logo(self, ega_mails[0])

    def test_several_addresses_can_be_configured(self):
        data = {
            "email": "multi@example.com", "first_name": "M", "last_name": "A",
            "department": "Econ", "country_code": "US", "motivation": "hi",
            "password1": "pass12345", "password2": "pass12345",
            "research_paper_1": SimpleUploadedFile("a.pdf", b"%PDF-1.4 a", content_type="application/pdf"),
            "research_paper_2": SimpleUploadedFile("b.pdf", b"%PDF-1.4 b", content_type="application/pdf"),
        }
        with override_settings(ADMIN_NOTIFY_EMAIL="ega@example.com, second@example.com"):
            self.client.post(reverse("apply_researcher"), data)
        self.assertEqual(
            [m.to for m in mail.outbox if m.reply_to == ["multi@example.com"]],
            [["ega@example.com", "second@example.com"]])

    def test_student_without_an_advisor_still_goes_to_the_shared_inbox(self):
        # The public form requires an advisor, but one can be missing (the advisor's
        # account was deleted, or an admin entered the application). Nobody else can
        # approve it, so the admins are told.
        from accounts.emails import send_application_submitted_email

        application = UserApplication.objects.create(
            email="orphan@example.com", first_name="Or", last_name="Phan",
            role=CustomUser.Role.STUDENT, password="x")
        send_application_submitted_email(application)
        self.assertEqual([m.to for m in mail.outbox], [["ega@example.com"]])

    def test_student_with_advisor_only_notifies_the_advisor(self):
        advisor = make_researcher()
        self.client.post(reverse("apply_student"), self._student_data(advisor=advisor.pk))
        self.assertEqual([m.to for m in mail.outbox], [[advisor.email]])

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
        self.assertTrue(advisor_mails[0].subject.startswith("[Action Required]"))
        self.assertEqual(
            advisor_mails[0].extra_headers.get("X-Cmail-GroupName"),
            "LaborHub")
        assert_has_html_alternative_with_logo(self, advisor_mails[0])
