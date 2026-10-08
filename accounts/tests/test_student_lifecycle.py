from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.forms import ResearcherApplicationForm, StudentApplicationForm
from accounts.models import CustomUser, UserApplication
from publications.models import Author, Publication


def make_student(email="stu@example.com", days_old=0, **fields):
    user = CustomUser.objects.create_user(
        email=email, password="pass12345", first_name="Sam", last_name="Student",
        role=CustomUser.Role.STUDENT, is_active=True, **fields)
    CustomUser.objects.filter(pk=user.pk).update(
        date_joined=timezone.now() - timedelta(days=days_old))
    user.refresh_from_db()
    return user


def run_command(*args):
    out = StringIO()
    call_command("deactivate_expired_students", *args, stdout=out)
    return out.getvalue()


class DeactivateExpiredStudentsTests(TestCase):
    def test_deactivates_after_two_years(self):
        user = make_student(days_old=731)
        run_command()
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_leaves_recent_students_alone(self):
        user = make_student(days_old=100)
        run_command()
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(len(mail.outbox), 0)

    def test_warns_once_30_days_before(self):
        user = make_student(days_old=705)
        run_command()
        run_command()
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.profile.deactivation_warned_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])

    def test_researchers_are_never_touched(self):
        researcher = CustomUser.objects.create_user(
            email="r@example.com", password="x", role=CustomUser.Role.RESEARCHER,
            is_active=True)
        CustomUser.objects.filter(pk=researcher.pk).update(
            date_joined=timezone.now() - timedelta(days=2000))
        run_command()
        researcher.refresh_from_db()
        self.assertTrue(researcher.is_active)

    def test_dry_run_changes_nothing(self):
        old, warn = make_student("a@example.com", 800), make_student("b@example.com", 710)
        run_command("--dry-run")
        old.refresh_from_db(), warn.refresh_from_db()
        self.assertTrue(old.is_active)
        self.assertIsNone(warn.profile.deactivation_warned_at)
        self.assertEqual(len(mail.outbox), 0)

    def test_deactivated_student_cannot_sign_in(self):
        user = make_student(days_old=731)
        run_command()
        self.assertFalse(self.client.login(email=user.email, password="pass12345"))


def application(**fields):
    data = dict(
        email="stu@example.com", first_name="Sam", last_name="Student",
        role=CustomUser.Role.RESEARCHER, position="Professor", department="Econ",
        password="hash", country_code="US")
    data.update(fields)
    return UserApplication.objects.create(**data)


class ReturningStudentApprovalTests(TestCase):
    def setUp(self):
        self.student = make_student(days_old=800)
        self.student.is_active = False
        self.student.save()
        self.old_password = self.student.password

    def test_same_email_reactivates_and_converts_the_account(self):
        paper = Publication.objects.create(title="Mine", abstract="x", status="approved")
        paper.authors.add(Author.objects.create(user=self.student, name="Sam Student"))
        user = application().approve()
        self.assertEqual(user.pk, self.student.pk)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(user.role, CustomUser.Role.RESEARCHER)
        self.assertIsNone(user.advisor)
        self.assertEqual(Publication.objects.get(pk=paper.pk).authors.get().user, user)
        self.assertEqual(CustomUser.objects.filter(email="stu@example.com").count(), 1)
        self.assertEqual(user.profile.position, "Professor")

    def test_existing_password_is_kept(self):
        application(password="attacker-chosen-hash").approve()
        self.student.refresh_from_db()
        self.assertEqual(self.student.password, self.old_password)

    def test_approval_email_points_at_the_existing_password(self):
        application().approve()
        body = mail.outbox[0].body
        self.assertIn("existing password", body)
        self.assertNotIn("the password you chose when you applied", body)

    def test_an_active_account_still_blocks_approval(self):
        self.student.is_active = True
        self.student.save()
        with self.assertRaises(ValueError):
            application().approve()

    def test_a_student_application_cannot_reuse_the_email(self):
        app = application(role=CustomUser.Role.STUDENT)
        self.assertIsNone(app.returning_student())


class ApplicationFormEmailTests(TestCase):
    def setUp(self):
        self.student = make_student()
        self.student.is_active = False
        self.student.save()

    def _errors(self, form_class, email="stu@example.com"):
        form = form_class({"email": email})
        form.is_valid()
        return form.errors.get("email")

    def test_researcher_form_accepts_a_deactivated_student_email(self):
        self.assertIsNone(self._errors(ResearcherApplicationForm))

    def test_student_form_still_rejects_it(self):
        self.assertTrue(self._errors(StudentApplicationForm))

    def test_researcher_form_rejects_an_active_account(self):
        make_student("live@example.com")
        self.assertTrue(self._errors(ResearcherApplicationForm, "live@example.com"))


class JobMarketPaperClaimTests(TestCase):
    def setUp(self):
        self.old_student = make_student("old@example.com")
        self.paper = Publication.objects.create(
            title="JM Paper", abstract="x", status="approved",
            is_job_market=True, job_market_paper_number=3)
        self.author = Author.objects.create(user=self.old_student, name="Sam Student")
        self.paper.authors.add(self.author)

    def _apply(self, number="J3", email="new@example.com", **fields):
        return application(
            email=email, previous_student_account=True,
            previous_jm_paper_number=number, **fields)

    def test_paper_moves_to_the_new_account(self):
        app = self._apply()
        user = app.approve()
        self.author.refresh_from_db()
        self.assertEqual(self.author.user, user)
        self.assertIn("attached", app.claim_note)

    def test_unknown_number_still_approves_with_a_note(self):
        app = self._apply("J99")
        app.approve()
        self.assertIn("not found", app.claim_note)

    def test_name_mismatch_attaches_nothing(self):
        app = self._apply(first_name="Someone", last_name="Else")
        app.approve()
        self.author.refresh_from_db()
        self.assertEqual(self.author.user, self.old_student)
        self.assertIn("not attached", app.claim_note)

    def test_unticked_box_claims_nothing(self):
        app = application(email="new@example.com", previous_jm_paper_number="J3")
        app.approve()
        self.author.refresh_from_db()
        self.assertEqual(self.author.user, self.old_student)

    def test_form_rejects_a_number_that_is_not_a_published_jm_paper(self):
        form = ResearcherApplicationForm({
            "email": "new@example.com", "previous_student_account": "on",
            "previous_jm_paper_number": "J99"})
        form.is_valid()
        self.assertIn("previous_jm_paper_number", form.errors)

    def test_form_accepts_a_real_number_and_a_blank_one(self):
        for number in ("J3", ""):
            form = ResearcherApplicationForm({
                "email": "new@example.com", "previous_student_account": "on",
                "previous_jm_paper_number": number})
            form.is_valid()
            self.assertNotIn("previous_jm_paper_number", form.errors, number)

    def test_apply_page_shows_the_question(self):
        page = self.client.get(reverse("apply_researcher"))
        self.assertContains(page, "previously have a student account")
        self.assertNotContains(
            self.client.get(reverse("apply_student")), "previously have a student account")


class DeactivatedNamesakeTests(TestCase):
    def test_author_name_matching_prefers_the_active_account(self):
        from publications.utils import handle_authors
        old = make_student("old@example.com")
        old.is_active = False
        old.save()
        new = CustomUser.objects.create_user(
            email="new@example.com", password="x", first_name="Sam", last_name="Student",
            role=CustomUser.Role.RESEARCHER, is_active=True)
        author = handle_authors('[{"value": "Sam Student"}]')[0]
        self.assertEqual(author.user, new)

    def test_account_search_skips_deactivated_users(self):
        old = make_student("old@example.com")
        old.is_active = False
        old.save()
        data = self.client.get(reverse("search_accounts"), {"q": "Sam"}).json()
        self.assertEqual(data, [])


class SendAlertsCommandTests(TestCase):
    def test_institution_only_subscribers_get_their_email(self):
        from seminars.models import Seminar, University
        university = University.objects.create(name="LSE", country_code="GB")
        user = make_student("alerts@example.com")
        user.profile.alert_universities = [university.pk]
        user.profile.save()
        Seminar.objects.create(
            visitor_name="V", status="approved", university=university,
            reviewed_at=timezone.now())
        call_command("send_alerts", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["alerts@example.com"])
