from django.template.loader import render_to_string
from django.test import TestCase


class HealthCheckTests(TestCase):
    def test_healthz_ok(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertEqual(response["Content-Type"], "text/plain")


class ErrorPageTests(TestCase):
    def test_404_uses_branded_template(self):
        # settings_test runs with DEBUG=False, so the 404 handler renders 404.html.
        response = self.client.get("/this-path-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Page not found", status_code=404)

    def test_500_template_renders_standalone(self):
        # The 500 page must render without request context / context processors.
        html = render_to_string("500.html")
        self.assertIn("Something went wrong", html)

    def test_400_template_renders_standalone(self):
        html = render_to_string("400.html")
        self.assertIn("Bad request", html)
