from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

ADDRESS = "Labor Hub, ILR School, Cornell University, Ithaca, NY 14853"


class LegalPagesTests(TestCase):
    def test_terms_and_privacy_render_and_cross_link(self):
        terms = self.client.get(reverse("terms"))
        privacy = self.client.get(reverse("privacy"))
        self.assertContains(terms, "Terms of Use")
        self.assertContains(terms, reverse("privacy"))
        self.assertContains(privacy, reverse("terms"))
        self.assertContains(privacy, "Campaign Monitor")
        self.assertContains(privacy, "Delete your account")

    def test_footer_links_terms_and_shows_the_address(self):
        response = self.client.get(reverse("privacy"))
        self.assertContains(response, f'href="{reverse("terms")}"')
        self.assertContains(response, ADDRESS)

    @override_settings(LABOR_HUB_POSTAL_ADDRESS="1 Test Road")
    def test_address_comes_from_the_setting(self):
        self.assertContains(self.client.get(reverse("contact")), "1 Test Road")
    def test_no_third_party_cdn_references_remain(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        hits = [
            str(path.relative_to(root))
            for path in (root / "templates").rglob("*.html")
            if "cdn.jsdelivr" in path.read_text() or "fonts.googleapis" in path.read_text()
        ]
        css = (root / "static/src/input.css").read_text()
        if "fonts.googleapis" in css:
            hits.append("static/src/input.css")
        self.assertEqual(hits, [])
