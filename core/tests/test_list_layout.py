from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser

LIST_URLS = (
    "events-list", "jobs-list", "seminars-list",
    "special-issues-list", "publications", "scholars",
)


class ListPageLayoutTests(TestCase):
    """Every list page shares one responsive layout (guards against per-page drift)."""

    def test_list_pages_use_the_shared_layout_classes(self):
        for name in LIST_URLS:
            with self.subTest(page=name):
                html = self.client.get(reverse(name)).content.decode()
                for cls in ("list-layout", "list-sidebar", "list-main",
                            "list-toolbar", "list-search", "list-actions", "btn-search"):
                    self.assertIn(cls, html)

    def test_search_input_has_no_icon_indent(self):
        for name in LIST_URLS:
            with self.subTest(page=name):
                html = self.client.get(reverse(name)).content.decode()
                self.assertNotIn('class="form-input ps-9"', html)

    def test_announcements_intro_sits_under_the_tabs(self):
        user = CustomUser.objects.create_user(
            email="a@example.com", password="x", first_name="A", last_name="B",
            role=CustomUser.Role.RESEARCHER, is_active=True)
        self.client.force_login(user)
        html = self.client.get(reverse("announcements")).content.decode()
        self.assertLess(html.index('aria-label="Announcement types"'), html.index('class="page-intro"'))
        self.assertIn(reverse("announcement-new"), html)
