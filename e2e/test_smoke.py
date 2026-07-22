"""Browser smoke tests for the critical and JavaScript-heavy user flows.

Opt-in; see ``e2e/base.py`` for how to run them. Selectors prefer roles,
labels, and stable ids over brittle CSS so they survive styling changes.
Each test builds its own data through the ORM so the run is deterministic
and hermetic (no external network is required).
"""
import re

from accounts.models import CustomUser
from publications.models import Publication

from .base import PlaywrightSmokeTestCase, expect

USER_EMAIL = "e2e@example.com"
USER_PASSWORD = "e2e-smoke-pass-123"


class SmokeTests(PlaywrightSmokeTestCase):
    def setUp(self):
        super().setUp()
        self.user = CustomUser.objects.create_user(
            email=USER_EMAIL,
            password=USER_PASSWORD,
            first_name="Test",
            last_name="Scholar",
            is_active=True,
        )

    def test_home_page_loads(self):
        """The home page renders with its title and navigation bar."""
        page = self.page
        page.goto(self.live_server_url + "/", wait_until="domcontentloaded")
        expect(page).to_have_title(re.compile("Labor Hub"))
        expect(page.locator("nav")).to_be_visible()

    def test_login_flow(self):
        """Logging in through the form lands the user with the account menu visible."""
        page = self.page
        self.login(USER_EMAIL, USER_PASSWORD)
        # The authenticated navbar shows the user's full name in the account menu.
        expect(page.get_by_role("button", name="Test Scholar")).to_be_visible()

    def test_contact_form_submits(self):
        """Submitting the public contact form shows the success confirmation."""
        page = self.page
        page.goto(self.url("contact"), wait_until="domcontentloaded")
        page.fill("#id_name", "Jane Tester")
        page.fill("#id_email", "jane@example.com")
        page.fill("#id_message", "Hello from an E2E smoke test.")
        page.get_by_role("button", name="Send message").click()
        expect(page.get_by_text("Thanks for reaching out")).to_be_visible()

    def test_submit_paper_page_renders(self):
        """The submit-a-paper form renders its heading and title field."""
        page = self.page
        page.goto(self.url("submit_paper"), wait_until="domcontentloaded")
        expect(
            page.get_by_role("heading", name=re.compile("Submit a paper", re.I))
        ).to_be_visible()
        expect(page.locator("#id_title")).to_be_visible()

    def test_world_map_country_click(self):
        """Clicking a country on the world map loads its side-panel details."""
        Publication.objects.create(
            title="E2E Map Paper",
            abstract="Abstract for the map smoke test.",
            study_url="https://example.com/e2e-map-paper",
            country_code="US",
            status="approved",
        )
        page = self.page
        page.goto(self.url("map"), wait_until="domcontentloaded")
        # Wait until map.js has initialised (it marks the active metric toggle).
        expect(page.locator("#toggle-users")).to_have_class(re.compile("is-active"))

        # Click the United States land path. Dispatch the DOM event directly so
        # the test does not depend on fragile SVG hit-test geometry.
        page.locator("#map-wrap path#US").dispatch_event("click")

        panel = page.locator("#map-panel")
        expect(panel.get_by_role("heading", name="United States")).to_be_visible()

        # The panel defaults to the scholars metric; switch to papers to reveal
        # the paper created above for the United States.
        page.locator("#toggle-papers").click()
        expect(panel.get_by_text("E2E Map Paper")).to_be_visible()
