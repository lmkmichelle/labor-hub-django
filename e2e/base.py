"""Base class and helpers for the Playwright browser smoke tests.

These tests drive a real Chromium browser against a live Django server
(``StaticLiveServerTestCase``) to exercise the JavaScript-heavy and
end-to-end critical flows that the Django test-client integration tests
cannot cover (the world map, real form submits, the login redirect).

They are **opt-in** so the default ``manage.py test`` run and the main CI
job stay fast and dependency-free. Every test in this package is skipped
(never errored) unless BOTH of the following are true:

* the ``RUN_E2E`` environment variable is set to ``1``, and
* the browser driver is installed::

      pip install -r requirements-dev.txt
      python -m playwright install chromium

Run them with::

    RUN_E2E=1 python manage.py test e2e --settings=nole.settings_test

``settings_test`` is required: it disables offline compression and the
HTTPS redirect and uses in-memory SQLite, all of which the live server
needs to serve pages to the browser.
"""
import os
import unittest

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls import reverse

RUN_E2E = os.environ.get("RUN_E2E") == "1"

try:
    from playwright.sync_api import sync_playwright, expect
    PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover - only hit where the dep is absent
    sync_playwright = None
    expect = None
    PLAYWRIGHT_AVAILABLE = False

_SKIP_REASON = (
    "Browser E2E tests are opt-in: set RUN_E2E=1 and run "
    "`pip install -r requirements-dev.txt && python -m playwright install chromium`."
)

# Playwright's sync API runs an asyncio event loop in the test thread, which makes
# Django's async-safety guard reject the ORM calls we use to seed test data. Those
# calls are genuinely synchronous and thread-confined, so opt out of the guard --
# but only when the E2E suite is actually active, so the normal test run keeps it.
if RUN_E2E and PLAYWRIGHT_AVAILABLE:
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")


@tag("e2e")
@unittest.skipUnless(RUN_E2E and PLAYWRIGHT_AVAILABLE, _SKIP_REASON)
class PlaywrightSmokeTestCase(StaticLiveServerTestCase):
    """Live-server test case with a shared Chromium browser and a fresh page per test."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._playwright = sync_playwright().start()
        cls.browser = cls._playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        browser = getattr(cls, "browser", None)
        if browser is not None:
            browser.close()
        playwright = getattr(cls, "_playwright", None)
        if playwright is not None:
            playwright.stop()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.set_default_timeout(15000)

    def tearDown(self):
        self.context.close()
        super().tearDown()

    def url(self, name, *args, **kwargs):
        """Absolute live-server URL for a named route (avoids hardcoded paths)."""
        return self.live_server_url + reverse(name, args=args, kwargs=kwargs)

    def login(self, email, password):
        """Log in through the real login form and wait for the resulting navigation."""
        page = self.page
        page.goto(self.url("login"), wait_until="domcontentloaded")
        page.fill("#id_username", email)
        page.fill("#id_password", password)
        with page.expect_navigation(wait_until="domcontentloaded"):
            page.get_by_role("button", name="Log in").click()
