import json

from django.contrib.auth.hashers import check_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from accounts.forms import (
    ResearcherApplicationForm,
    StudentApplicationForm,
    UpdateProfileForm,
)
from accounts.models import CustomUser, UserApplication
from publications.models import Author, Publication


def _pdf(name):
    return SimpleUploadedFile(name, b"%PDF-1.4 fake", content_type="application/pdf")


def both_papers():
    return {"research_paper_1": _pdf("p1.pdf"), "research_paper_2": _pdf("p2.pdf")}


def base_application_data(**overrides):
    data = {
        "email": "applicant@example.com",
        "first_name": "Ann",
        "last_name": "Applicant",
        "department": "Cornell",
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
        form = ResearcherApplicationForm(files=both_papers(), data=base_application_data())
        self.assertTrue(form.is_valid(), form.errors)
        application = form.save()
        self.assertIsNotNone(application.pk)
        self.assertEqual(application.role, CustomUser.Role.RESEARCHER)
        self.assertEqual(application.status, UserApplication.Status.PENDING)
        self.assertNotEqual(application.password, "pass12345")
        self.assertTrue(check_password("pass12345", application.password))

    def test_password_mismatch_is_invalid(self):
        form = ResearcherApplicationForm(
            files=both_papers(), data=base_application_data(password2="different"))
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_duplicate_user_email_is_invalid(self):
        make_researcher(email="applicant@example.com")
        form = ResearcherApplicationForm(files=both_papers(), data=base_application_data())
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_duplicate_pending_application_email_is_invalid(self):
        UserApplication.objects.create(
            email="applicant@example.com", first_name="X", last_name="Y",
            position="p", department="e", password="x",
            status=UserApplication.Status.PENDING,
        )
        form = ResearcherApplicationForm(files=both_papers(), data=base_application_data())
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_optional_website_is_saved(self):
        form = ResearcherApplicationForm(
            files=both_papers(), data=base_application_data(website="https://example.org/me"))
        self.assertTrue(form.is_valid(), form.errors)
        application = form.save()
        self.assertEqual(application.website, "https://example.org/me")

    def test_optional_cv_url_is_saved(self):
        form = ResearcherApplicationForm(
            files=both_papers(), data=base_application_data(cv_url="https://example.org/my-cv"))
        self.assertTrue(form.is_valid(), form.errors)
        application = form.save()
        self.assertEqual(application.cv_url, "https://example.org/my-cv")

    def test_invalid_cv_url_is_rejected(self):
        form = ResearcherApplicationForm(
            files=both_papers(), data=base_application_data(cv_url="not-a-url"))
        self.assertFalse(form.is_valid())
        self.assertIn("cv_url", form.errors)

    def test_other_networks_default_to_empty(self):
        form = ResearcherApplicationForm(files=both_papers(), data=base_application_data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().other_networks, [])

    def test_other_networks_saved_with_urls_in_choice_order(self):
        form = ResearcherApplicationForm(files=both_papers(), data=base_application_data(
            other_networks=["IZA", "NBER"],
            network_url_nber="https://nber.org/me",
            network_url_iza="https://iza.org/me",
        ))
        self.assertTrue(form.is_valid(), form.errors)
        application = form.save()
        self.assertEqual(application.other_networks, [
            {"network": "NBER", "url": "https://nber.org/me"},
            {"network": "IZA", "url": "https://iza.org/me"},
        ])

    def test_url_for_an_unchecked_network_is_discarded(self):
        form = ResearcherApplicationForm(files=both_papers(), data=base_application_data(
            other_networks=["NBER"],
            network_url_nber="https://nber.org/me",
            network_url_cepr="https://cepr.org/ghost",
        ))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().other_networks, [
            {"network": "NBER", "url": "https://nber.org/me"},
        ])

    def test_checked_network_without_a_url_is_allowed(self):
        form = ResearcherApplicationForm(files=both_papers(), data=base_application_data(
            other_networks=["CESifo"]))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().other_networks, [
            {"network": "CESifo", "url": ""},
        ])

    def test_both_research_papers_are_required(self):
        form = ResearcherApplicationForm(data=base_application_data(), files={})
        self.assertFalse(form.is_valid())
        self.assertIn("research_paper_1", form.errors)
        self.assertIn("research_paper_2", form.errors)
        self.assertEqual(form.errors["research_paper_1"], ["Please upload both research papers."])

    def test_only_one_research_paper_is_rejected(self):
        form = ResearcherApplicationForm(
            data=base_application_data(), files={"research_paper_1": _pdf("p1.pdf")})
        self.assertFalse(form.is_valid())
        self.assertNotIn("research_paper_1", form.errors)
        self.assertIn("research_paper_2", form.errors)

    def test_both_research_paper_slots_filled_is_accepted(self):
        files = {
            "research_paper_1": _pdf("p1.pdf"),
            "research_paper_2": _pdf("p2.pdf"),
        }
        form = ResearcherApplicationForm(
            data=base_application_data(), files=files)
        self.assertTrue(form.is_valid(), form.errors)

    def test_networks_accept_tagify_json_comma_text_and_lists(self):
        for i, value in enumerate(('[{"value":"IZA"},{"value":"NBER"}]', "IZA,NBER", ["IZA", "NBER"])):
            with self.subTest(value=value):
                form = ResearcherApplicationForm(
                    files=both_papers(),
                    data=base_application_data(email=f"net{i}@example.com", other_networks=value))
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(
                    [n["network"] for n in form.save().other_networks], ["NBER", "IZA"])

    def test_unknown_network_is_rejected(self):
        form = ResearcherApplicationForm(
            files=both_papers(),
            data=base_application_data(other_networks='[{"value":"Made Up"}]'))
        self.assertFalse(form.is_valid())
        self.assertIn("other_networks", form.errors)


class PreviousJobMarketPaperTests(TestCase):
    def _jm(self, number, title="A Job Market Paper", **kw):
        paper = Publication.objects.create(
            title=title, abstract="a", status="approved", is_job_market=True,
            job_market_paper_number=number, **kw)
        paper.authors.add(Author.objects.create(user=None, name="Jo Candidate"))
        return paper

    def _form(self, value, ticked=True):
        data = base_application_data(previous_jm_paper_number=value)
        if ticked:
            data["previous_student_account"] = "on"
        return ResearcherApplicationForm(data=data, files=both_papers())

    def test_a_picked_paper_is_stored_as_its_j_number(self):
        paper = self._jm(3)
        form = self._form(json.dumps([{"value": "[J3] A Job Market Paper", "id": paper.pk}]))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().previous_jm_paper_number, "J3")

    def test_whitelist_lists_published_job_market_papers_with_authors(self):
        paper = self._jm(3)
        Publication.objects.create(title="Pending", abstract="a", status="pending",
                                   is_job_market=True, job_market_paper_number=9)
        Publication.objects.create(title="Regular", abstract="a", status="approved",
                                   discussion_paper_number=7)
        whitelist = self._form("").jm_paper_whitelist
        self.assertEqual(whitelist, [
            {"value": "[J3] A Job Market Paper (Jo Candidate)", "id": paper.pk}])

    def test_an_id_that_is_not_a_published_job_market_paper_is_rejected(self):
        regular = Publication.objects.create(
            title="Regular", abstract="a", status="approved", discussion_paper_number=7)
        form = self._form(json.dumps([{"value": "x", "id": regular.pk}]))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["previous_jm_paper_number"],
                         ["Choose a job market paper from the list."])

    def test_a_typed_number_still_works_for_other_clients(self):
        self._jm(3)
        form = self._form("J3")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().previous_jm_paper_number, "J3")

    def test_empty_pill_and_unticked_box_are_ignored(self):
        paper = self._jm(3)
        self.assertEqual(self._form("[]").save().previous_jm_paper_number, "")
        unticked = ResearcherApplicationForm(
            files=both_papers(), data=base_application_data(
                email="unticked@example.com",
                previous_jm_paper_number=json.dumps([{"value": "x", "id": paper.pk}])))
        self.assertTrue(unticked.is_valid(), unticked.errors)
        self.assertEqual(unticked.save().previous_jm_paper_number, "")


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
