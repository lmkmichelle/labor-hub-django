"""Tests for the static footer pages (About/Privacy/Accessibility) and the
auth-aware footer links."""

from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser


class StaticPageTests(TestCase):
    def test_pages_render(self):
        cases = [
            ('about', 'core/about.html'),
            ('privacy', 'core/privacy.html'),
            ('accessibility', 'core/accessibility.html'),
        ]
        for name, template in cases:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)


class FooterLinkTests(TestCase):
    def test_common_links_present_for_anonymous(self):
        response = self.client.get(reverse('home'))
        for name in ('about', 'contact', 'privacy', 'accessibility'):
            self.assertContains(response, f'href="{reverse(name)}"')
        # Anonymous visitors see "Sign in", not "Submit a paper".
        self.assertContains(response, f'href="{reverse("login")}"')
        self.assertNotContains(response, f'href="{reverse("submit_paper")}"')

    def test_submit_paper_shown_when_authenticated(self):
        user = CustomUser.objects.create_user(
            email='footer@example.com', password='footer-test-pw',
            first_name='Foo', last_name='Ter',
            role=CustomUser.Role.RESEARCHER, is_active=True,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertContains(response, f'href="{reverse("submit_paper")}"')
