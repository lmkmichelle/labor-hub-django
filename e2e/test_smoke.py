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
        self.login(USER_EMAIL, USER_PASSWORD)
        page.goto(self.url("submit_paper"), wait_until="domcontentloaded")
        expect(
            page.get_by_role("heading", name=re.compile("Submit a paper", re.I))
        ).to_be_visible()
        expect(page.locator("#id_title")).to_be_visible()

    def test_paper_type_cards_reveal_their_own_fields(self):
        """Each paper-type card shows only its own sub-panel, and the revision
        picker offers the user's published papers as a single pill."""
        from publications.models import Author

        paper = Publication.objects.create(
            title="Wages and Work", abstract="a", status="approved",
            discussion_paper_number=323, submitted_by=self.user)
        paper.authors.add(Author.objects.create(user=self.user, name="Test Scholar"))
        page = self.page
        self.login(USER_EMAIL, USER_PASSWORD)
        page.goto(self.url("submit_paper"), wait_until="domcontentloaded")

        advisor, revision = page.locator("#id_jm_advisor"), page.locator("#revision-of-input")
        expect(advisor).to_be_hidden()
        page.get_by_text("Job market paper", exact=True).click()
        expect(advisor).to_be_visible()
        page.get_by_text("Revision of a previous paper", exact=True).click()
        expect(advisor).to_be_hidden()

        # The pill picker needs Tagify (loaded from a CDN); skip if it can't load.
        try:
            page.wait_for_selector("tags.tagify", timeout=5000)
        except Exception:
            self.skipTest("Tagify did not load (no network)")
        picker = page.locator(
            'tags.tagify:has(.tagify__input[data-placeholder="Choose the paper you are revising"])')
        picker.locator(".tagify__input").click()
        page.get_by_text("[323] Wages and Work").click()
        expect(picker.locator(".tagify__tag")).to_have_count(1)
        self.assertIn(f'"id":{paper.pk}', revision.input_value())

    def _tagify_or_skip(self, page):
        try:
            page.wait_for_selector("tags.tagify", timeout=5000)
        except Exception:
            self.skipTest("Tagify did not load (no network)")

    def test_application_network_pills_reveal_their_url_field(self):
        """Choosing a network pill shows that network's URL box; removing it hides it."""
        page = self.page
        page.goto(self.url("apply_researcher"), wait_until="domcontentloaded")
        self._tagify_or_skip(page)
        nber = page.locator("#id_network_url_nber")
        expect(nber).to_be_hidden()
        picker = page.locator(
            'tags.tagify:has(.tagify__input[data-placeholder="Choose from the list"])')
        picker.locator(".tagify__input").click()
        page.locator(".tagify__dropdown__item", has_text="NBER").click()
        expect(nber).to_be_visible()
        expect(page.locator("#id_network_url_iza")).to_be_hidden()
        picker.locator(".tagify__tag__removeBtn").click()
        expect(nber).to_be_hidden()

    def test_application_previous_job_market_paper_is_picked_not_typed(self):
        from publications.models import Author

        paper = Publication.objects.create(
            title="Do Firms Know", abstract="a", status="approved",
            is_job_market=True, job_market_paper_number=3)
        paper.authors.add(Author.objects.create(user=None, name="Jo Candidate"))
        page = self.page
        page.goto(self.url("apply_researcher"), wait_until="domcontentloaded")
        self._tagify_or_skip(page)
        picker_input = page.locator("#previous-jm-input")
        page.locator("#id_previous_student_account").check()
        picker = page.locator(
            'tags.tagify:has(.tagify__input[data-placeholder="Choose your job market paper"])')
        expect(picker).to_be_visible()
        picker.locator(".tagify__input").click()
        page.get_by_text("[J3] Do Firms Know (Jo Candidate)").click()
        self.assertIn(f'"id":{paper.pk}', picker_input.input_value())

    def test_application_upload_slots_cv_switch_and_counter(self):
        page = self.page
        page.goto(self.url("apply_researcher"), wait_until="domcontentloaded")
        counter = page.locator("[data-upload-counter]")
        expect(counter).to_have_text("0 of 2 added")
        pdf = {"name": "a.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4 a"}
        page.set_input_files("#id_research_paper_1", pdf)
        expect(counter).to_have_text("1 of 2 added")
        expect(page.locator("[data-upload-group] [data-upload-name]").first).to_have_text("a.pdf")
        page.set_input_files(
            "#id_research_paper_2", {**pdf, "name": "notes.txt", "mimeType": "text/plain"})
        expect(page.get_by_text("Please choose a PDF file.")).to_be_visible()
        expect(counter).to_have_text("1 of 2 added")
        page.locator("[data-upload-group] [data-upload-remove]").first.click()
        expect(counter).to_have_text("0 of 2 added")

        # CV: a link or an upload, never both showing.
        expect(page.locator("#id_cv_url")).to_be_visible()
        expect(page.locator("#id_resume")).to_be_hidden()
        page.get_by_text("Upload PDF", exact=True).click()
        expect(page.locator("[data-cv-panel='upload']")).to_be_visible()
        expect(page.locator("#id_cv_url")).to_be_hidden()

    def test_links_and_link_buttons_are_not_underlined(self):
        page = self.page

        def decoration(locator):
            return locator.evaluate("el => getComputedStyle(el).textDecorationLine")

        page.goto(self.url("login"), wait_until="domcontentloaded")
        for link in (page.get_by_role("link", name="Cancel"),
                     page.get_by_role("link", name="Forgot your password?")):
            self.assertEqual(decoration(link), "none")
            link.hover()
            self.assertEqual(decoration(link), "none" if link.inner_text() == "Cancel" else "underline")

        # A plain prose link: red, not underlined, underlined only on hover.
        page.goto(self.url("faq"), wait_until="domcontentloaded")
        prose = page.get_by_role("link", name="Get in touch")
        self.assertEqual(decoration(prose), "none")
        self.assertEqual(
            prose.evaluate("el => getComputedStyle(el).color"), "oklch(0.505 0.213 27.518)")  # Tailwind red-700
        prose.hover()
        self.assertEqual(decoration(prose), "underline")

    def test_world_map_country_click(self):
        """Clicking a country on the world map loads its side-panel details."""
        Publication.objects.create(
            title="E2E Map Paper",
            abstract="Abstract for the map smoke test.",
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

    def test_institution_field_hidden_until_country_is_picked(self):
        """Regression: static/js/university-picker.js hid `.closest(".mb-5")`,
        a wrapper class the form partials stopped using, so the Affiliation
        select (and its write-in text fallback) never actually hid. Both
        must start hidden and only appear after a country is selected."""
        page = self.page
        page.goto(self.url("apply_researcher"), wait_until="domcontentloaded")

        university_field = page.locator("#id_university").locator(
            "xpath=ancestor::div[contains(@class, 'form-field')]")
        university_name_field = page.locator("#id_university_name").locator(
            "xpath=ancestor::div[contains(@class, 'form-field')]")

        expect(university_field).to_be_hidden()
        expect(university_name_field).to_be_hidden()

        # Picking a country makes the picker fetch that country's universities.
        # Wait for the response so no request is still in flight when the test
        # ends: it would hold a lock on the shared in-memory SQLite database and
        # break the *next* test's teardown (a different test failed each run).
        with page.expect_response("**/visits/universities/**"):
            page.select_option("#id_country_code", "US")

        expect(university_field).to_be_visible()
        expect(university_name_field).to_be_visible()
