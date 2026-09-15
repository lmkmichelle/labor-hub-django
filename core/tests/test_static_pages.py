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


class NavbarContactLinkTests(TestCase):
    """"Contact Us" appears in the top nav (not just the footer) for everyone."""

    def test_present_for_anonymous_and_authenticated(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Contact Us')

        user = CustomUser.objects.create_user(
            email='navcontact@example.com', password='navcontact-test-pw',
            first_name='Nav', last_name='Contact',
            role=CustomUser.Role.RESEARCHER, is_active=True,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Contact Us')

    def test_highlighted_on_contact_page(self):
        response = self.client.get(reverse('contact'))
        self.assertContains(response, 'class="nav-link whitespace-nowrap text-red-700">Contact Us')


class NavbarPostLinksTests(TestCase):
    """The logged-in user dropdown offers Post a Job/Visit/Event alongside
    Submit a paper; anonymous visitors see none of them."""

    post_link_names = ('job-create', 'seminar-create', 'event-create')

    def test_hidden_for_anonymous(self):
        response = self.client.get(reverse('home'))
        for name in self.post_link_names:
            self.assertNotContains(response, f'href="{reverse(name)}"')

    def test_shown_when_authenticated(self):
        user = CustomUser.objects.create_user(
            email='navbar@example.com', password='navbar-test-pw',
            first_name='Nav', last_name='Bar',
            role=CustomUser.Role.RESEARCHER, is_active=True,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        for name in self.post_link_names:
            self.assertContains(response, f'href="{reverse(name)}"')
