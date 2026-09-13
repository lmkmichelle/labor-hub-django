from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import CustomUser
from publications.models import Author, Publication


def make_researcher(email="advisor@example.com"):
    return CustomUser.objects.create_user(
        email=email, password="pass12345", first_name="Ada", last_name="Visor",
        role=CustomUser.Role.RESEARCHER, is_active=True,
    )


def make_jm_paper(advisor, title="JM Paper", acknowledged=None, **extra):
    return Publication.objects.create(
        title=title, abstract="a", status="approved",
        is_job_market=True, jm_advisor=advisor,
        jm_advisor_acknowledged=acknowledged, **extra,
    )


class AdvisedPapersListTests(TestCase):
    def test_login_required(self):
        response = self.client.get(reverse("advised_papers"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_lists_only_own_job_market_papers(self):
        advisor = make_researcher()
        other = make_researcher(email="other@example.com")
        mine = make_jm_paper(advisor, title="Mine")
        make_jm_paper(other, title="Theirs")
        # A non-job-market paper naming the advisor must not appear.
        Publication.objects.create(
            title="Not JM", abstract="a", status="approved",
            is_job_market=False, jm_advisor=advisor)

        self.client.force_login(advisor)
        response = self.client.get(reverse("advised_papers"))
        self.assertEqual(list(response.context["papers"]), [mine])

    def test_pending_papers_sort_before_answered_ones(self):
        advisor = make_researcher()
        answered = make_jm_paper(advisor, title="Answered", acknowledged=True)
        pending = make_jm_paper(advisor, title="Pending")
        self.client.force_login(advisor)
        response = self.client.get(reverse("advised_papers"))
        self.assertEqual(list(response.context["papers"]), [pending, answered])

    def test_empty_state_for_a_researcher_with_none(self):
        self.client.force_login(make_researcher())
        response = self.client.get(reverse("advised_papers"))
        self.assertEqual(list(response.context["papers"]), [])


class PaperAckActionTests(TestCase):
    def setUp(self):
        self.advisor = make_researcher()
        self.paper = make_jm_paper(self.advisor)

    def test_confirm_records_yes_and_timestamp(self):
        self.client.force_login(self.advisor)
        response = self.client.post(
            reverse("paper_ack_confirm", args=[self.paper.pk]))
        self.assertRedirects(response, reverse("advised_papers"))
        self.paper.refresh_from_db()
        self.assertIs(self.paper.jm_advisor_acknowledged, True)
        self.assertIsNotNone(self.paper.jm_advisor_responded_at)

    def test_decline_records_no(self):
        self.client.force_login(self.advisor)
        self.client.post(reverse("paper_ack_decline", args=[self.paper.pk]))
        self.paper.refresh_from_db()
        self.assertIs(self.paper.jm_advisor_acknowledged, False)

    def test_a_second_response_is_rejected(self):
        self.client.force_login(self.advisor)
        self.client.post(reverse("paper_ack_confirm", args=[self.paper.pk]))
        first = Publication.objects.get(pk=self.paper.pk).jm_advisor_responded_at
        self.client.post(reverse("paper_ack_decline", args=[self.paper.pk]))
        again = Publication.objects.get(pk=self.paper.pk)
        self.assertIs(again.jm_advisor_acknowledged, True)
        self.assertEqual(again.jm_advisor_responded_at, first)

    def test_another_researchers_paper_404s(self):
        intruder = make_researcher(email="intruder@example.com")
        self.client.force_login(intruder)
        response = self.client.post(
            reverse("paper_ack_confirm", args=[self.paper.pk]))
        self.assertEqual(response.status_code, 404)
        self.paper.refresh_from_db()
        self.assertIsNone(self.paper.jm_advisor_acknowledged)

    def test_get_is_not_allowed(self):
        self.client.force_login(self.advisor)
        response = self.client.get(
            reverse("paper_ack_confirm", args=[self.paper.pk]))
        self.assertEqual(response.status_code, 405)


class PaperAckBadgeTests(TestCase):
    def test_count_only_for_researchers_with_pending_papers(self):
        advisor = make_researcher()
        make_jm_paper(advisor)
        make_jm_paper(advisor, title="Answered", acknowledged=True)
        self.client.force_login(advisor)
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["pending_paper_ack_count"], 1)

    def test_count_is_zero_for_anonymous(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["pending_paper_ack_count"], 0)

    def test_count_is_zero_for_students(self):
        student = CustomUser.objects.create_user(
            email="s@example.com", password="pass12345", first_name="S",
            last_name="T", role=CustomUser.Role.STUDENT, is_active=True)
        self.client.force_login(student)
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["pending_paper_ack_count"], 0)


@override_settings(SITE_URL="https://laborhub.test")
class PaperAdvisorEmailTests(TestCase):
    def _submit_data(self, advisor=None):
        data = {
            "title": "Submitted JM Paper",
            "abstract": "a",
            "country_code": "US",
            "authors_input": '[{"value":"Jane Doe"}]',
            "topics_input": '[{"value":"Labor Supply"}]',
            "is_job_market": "on",
        }
        if advisor is not None:
            data["jm_advisor"] = advisor.pk
        return data

    def test_job_market_submission_emails_the_advisor(self):
        submitter = CustomUser.objects.create_user(
            email="submitter@example.com", password="pass12345",
            first_name="Sam", last_name="Submitter", is_active=True)
        advisor = make_researcher()
        self.client.force_login(submitter)
        self.client.post(reverse("submit_paper"), self._submit_data(advisor))

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [advisor.email])
        self.assertIn("https://laborhub.test" + reverse("advised_papers"),
                      message.body)

    def test_non_job_market_submission_sends_nothing(self):
        submitter = CustomUser.objects.create_user(
            email="s2@example.com", password="pass12345", first_name="S",
            last_name="T", is_active=True)
        self.client.force_login(submitter)
        data = self._submit_data()
        data["is_job_market"] = ""
        self.client.post(reverse("submit_paper"), data)
        self.assertEqual(len(mail.outbox), 0)
