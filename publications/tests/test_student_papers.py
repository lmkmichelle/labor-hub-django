from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from publications.forms import PublicationForm
from publications.models import Author, Publication
from publications.tests.test_revisions import pick
from publications.tests.test_views import create_post_data, make_publication, make_user


def make_student(email="stu@example.com"):
    return CustomUser.objects.create_user(
        email=email, password="pass12345", first_name="Stu", last_name="Dent",
        role=CustomUser.Role.STUDENT, is_active=True)


def student_jm_paper(student, advisor, **fields):
    paper = make_publication(
        status="approved", is_job_market=True, job_market_paper_number=1, jm_advisor=advisor,
        jm_advisor_acknowledged=True, **fields)
    paper.authors.add(Author.objects.get_or_create(user=student, name="Stu Dent")[0])
    return paper


class StudentPaperTypeTests(TestCase):
    def setUp(self):
        self.advisor = make_user(email="adv@example.com", first_name="Ad", last_name="Visor")
        self.student = make_student()

    def test_student_has_no_discussion_card(self):
        form = PublicationForm(user=self.student)
        self.assertEqual([c[0] for c in form.fields["paper_type"].choices],
                         ["job_market", "revision"])
        self.assertEqual(form.fields["paper_type"].initial, "job_market")

    def test_fellow_keeps_all_three_cards(self):
        form = PublicationForm(user=self.advisor)
        self.assertEqual(len(form.fields["paper_type"].choices), 3)

    def test_student_cannot_post_a_discussion_paper(self):
        form = PublicationForm(create_post_data(paper_type="discussion"), user=self.student)
        self.assertFalse(form.is_valid())
        self.assertIn("paper_type", form.errors)

    def test_student_can_only_revise_job_market_papers(self):
        jm = student_jm_paper(self.student, self.advisor)
        dp = make_publication(status="approved", discussion_paper_number=5)
        dp.authors.add(Author.objects.get_or_create(user=self.student, name="Stu Dent")[0])
        self.assertEqual(PublicationForm(user=self.student).revisable, [jm])

    def test_student_revision_goes_back_to_the_advisor(self):
        original = student_jm_paper(self.student, self.advisor)
        self.client.force_login(self.student)
        self.client.post(reverse("submit_paper"), create_post_data(
            paper_type="revision", revision_of_input=pick(original)))
        revision = Publication.objects.get(title="New Paper")
        self.assertIsNone(revision.jm_advisor_acknowledged)
        self.assertEqual(revision.jm_advisor, self.advisor)
        self.assertEqual([m.to for m in mail.outbox], [[self.advisor.email]])

    def test_fellow_revision_still_inherits_the_response(self):
        original = student_jm_paper(self.advisor, self.advisor)
        self.client.force_login(self.advisor)
        self.client.post(reverse("submit_paper"), create_post_data(
            paper_type="revision", revision_of_input=pick(original)))
        revision = Publication.objects.get(title="New Paper")
        self.assertTrue(revision.jm_advisor_acknowledged)
        self.assertEqual(mail.outbox, [])
