"""Access control and rendering for the superuser-only admin guides.

The guides document moderation workflows and link straight into Django admin, so
they must never be reachable by an ordinary member.
"""
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser

HELP_PAGES = [
    ("help_index", "core/help/index.html"),
    ("help_applications", "core/help/applications.html"),
    ("help_content", "core/help/content.html"),
]


def make_user(email, **extra):
    return CustomUser.objects.create_user(
        email=email,
        password="pass12345",
        first_name="First",
        last_name="Last",
        is_active=True,
        **extra,
    )


class HelpPageAccessTests(TestCase):
    def test_anonymous_is_sent_to_the_login_page(self):
        """Signing in may grant access, so anonymous users get the login form."""
        for name, _ in HELP_PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response.url)

    def test_anonymous_redirect_lands_on_a_page_that_exists(self):
        response = self.client.get(reverse("help_index"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")

    def test_ordinary_member_is_forbidden(self):
        """A signed-in member gets 403, not a login form they cannot act on."""
        self.client.force_login(make_user("member@example.com"))
        for name, _ in HELP_PAGES:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_staff_without_superuser_is_forbidden(self):
        """is_staff opens Django admin but must not open the guides."""
        self.client.force_login(make_user("staff@example.com", is_staff=True))
        for name, _ in HELP_PAGES:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_superuser_sees_every_page(self):
        self.client.force_login(
            make_user("boss@example.com", is_staff=True, is_superuser=True)
        )
        for name, template in HELP_PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)


class HelpPageContentTests(TestCase):
    def setUp(self):
        self.client.force_login(
            make_user("boss@example.com", is_staff=True, is_superuser=True)
        )

    def test_index_links_to_every_pending_queue(self):
        """There is no cross-type pending dashboard, so these links are the substitute."""
        response = self.client.get(reverse("help_index"))
        for changelist in [
            "admin:accounts_userapplication_changelist",
            "admin:publications_publication_changelist",
            "admin:events_event_changelist",
            "admin:jobs_job_changelist",
            "admin:seminars_seminar_changelist",
        ]:
            with self.subTest(changelist=changelist):
                self.assertContains(
                    response, f"{reverse(changelist)}?status__exact=pending"
                )

    def test_index_links_to_both_guides(self):
        response = self.client.get(reverse("help_index"))
        self.assertContains(response, reverse("help_applications"))
        self.assertContains(response, reverse("help_content"))

    def test_pages_use_the_wired_up_title_block(self):
        response = self.client.get(reverse("help_applications"))
        self.assertContains(response, "<title>Approving new members</title>")


class HelpNavLinkTests(TestCase):
    def test_superuser_sees_the_dropdown_link(self):
        self.client.force_login(
            make_user("boss@example.com", is_staff=True, is_superuser=True)
        )
        response = self.client.get(reverse("home"))
        self.assertContains(response, reverse("help_index"))

    def test_ordinary_member_does_not_see_the_dropdown_link(self):
        self.client.force_login(make_user("member@example.com"))
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, reverse("help_index"))

    def test_staff_without_superuser_does_not_see_the_dropdown_link(self):
        self.client.force_login(make_user("staff@example.com", is_staff=True))
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, reverse("help_index"))
