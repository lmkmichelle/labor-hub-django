from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser, Profile, UserApplication


class ApplicationConsentTests(TestCase):
    def test_apply_page_discloses_and_links_the_terms(self):
        response = self.client.get(reverse("apply_researcher"))
        self.assertContains(response, "shown publicly on the site")
        self.assertContains(response, "record opens and clicks")
        self.assertContains(response, reverse("terms"))
        self.assertContains(response, reverse("privacy"))
        self.assertContains(response, 'name="newsletter_frequency"')

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
