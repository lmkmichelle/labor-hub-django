from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser, Profile, UserApplication


class ApplicationConsentTests(TestCase):
    def test_apply_page_discloses_and_links_the_terms(self):
        response = self.client.get(reverse("apply_researcher"))
        self.assertContains(response, 'name="agree_terms"')
        self.assertContains(response, "shown publicly on the site")
        self.assertContains(response, "record opens and clicks")
        self.assertContains(response, f'href="{reverse("terms")}"')
        self.assertContains(response, f'href="{reverse("privacy")}"')
        self.assertContains(response, 'name="newsletter_frequency"')

    def test_unticked_agreement_blocks_the_application(self):
        from accounts.forms import StudentApplicationForm  # noqa: F401
        from accounts.tests.test_forms import base_application_data, both_papers
        from accounts.forms import ResearcherApplicationForm

        data = base_application_data()
        data.pop("agree_terms")
        form = ResearcherApplicationForm(data=data, files=both_papers())
        self.assertFalse(form.is_valid())
        self.assertIn("agree_terms", form.errors)

    def test_agreement_time_is_recorded(self):
        from accounts.forms import ResearcherApplicationForm
        from accounts.tests.test_forms import base_application_data, both_papers

        form = ResearcherApplicationForm(
            data=base_application_data(), files=both_papers())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNotNone(form.save().terms_accepted_at)

    def test_choice_is_copied_to_the_profile_on_approval(self):
        application = UserApplication.objects.create(
            email="new@example.com", first_name="New", last_name="Member",
            role=CustomUser.Role.RESEARCHER, password="x",
            newsletter_frequency=Profile.NewsletterFrequency.MONTHLY,
        )
        application.approve()
        user = CustomUser.objects.get(email="new@example.com")
        self.assertEqual(
            user.profile.newsletter_frequency, Profile.NewsletterFrequency.MONTHLY)
