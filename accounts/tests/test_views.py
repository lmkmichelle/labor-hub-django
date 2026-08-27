from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import CustomUser, ResearchPaper, UserApplication


def make_active_user(email="user@example.com", password="pass12345",
                     role=CustomUser.Role.RESEARCHER):
    return CustomUser.objects.create_user(
        email=email, password=password, first_name="First", last_name="Last",
        role=role, is_active=True,
    )


def make_image_file(name="avatar.png"):
    buffer = BytesIO()
    Image.new("RGB", (400, 400), "blue").save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/png")


def application_post_data(**overrides):
    data = {
        "email": "applicant@example.com",
        "first_name": "Ann",
        "last_name": "Applicant",
        "department": "Cornell",
        "country_code": "US",
        "motivation": "Please let me in.",
        "password1": "pass12345",
        "password2": "pass12345",
    }
    data.update(overrides)
    return data


class MembershipPageTests(TestCase):
    def test_membership_page_renders_with_apply_links(self):
        response = self.client.get(reverse("membership"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/apply_landing.html")
        content = response.content.decode()
        self.assertIn("<h2>Apply</h2>", content)
        self.assertIn("How do I become a member?", content)
        self.assertIn(reverse("apply_student"), content)
        self.assertIn(reverse("apply_researcher"), content)


class ApplicationViewTests(TestCase):
    def test_apply_researcher_get(self):
        response = self.client.get(reverse("apply_researcher"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/apply.html")
        self.assertEqual(response.context["application_type"], "Researcher")

    def test_apply_student_get(self):
        response = self.client.get(reverse("apply_student"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["application_type"], "Student")

    def test_apply_researcher_post_creates_application(self):
        response = self.client.post(
            reverse("apply_researcher"), application_post_data())
        self.assertRedirects(
            response, reverse("application_submitted"),
            fetch_redirect_response=False)
        application = UserApplication.objects.get(email="applicant@example.com")
        self.assertEqual(application.role, CustomUser.Role.RESEARCHER)
        self.assertEqual(application.status, UserApplication.Status.PENDING)

    def test_apply_researcher_post_with_paper_creates_research_paper(self):
        data = application_post_data()
        data["research_papers"] = SimpleUploadedFile(
            "paper.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        response = self.client.post(reverse("apply_researcher"), data)
        self.assertEqual(response.status_code, 302)
        application = UserApplication.objects.get(email="applicant@example.com")
        self.assertEqual(
            ResearchPaper.objects.filter(application=application).count(), 1)


class LoginViewTests(TestCase):
    def test_login_get(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_login_post_valid_authenticates(self):
        make_active_user(email="login@example.com", password="pass12345")
        response = self.client.post(
            reverse("login"),
            {"username": "login@example.com", "password": "pass12345"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)


class ProfileViewTests(TestCase):
    def test_profile_by_pk_renders(self):
        user = make_active_user()
        response = self.client.get(reverse("profile", kwargs={"pk": user.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile.html")

    def test_profile_unknown_pk_returns_404(self):
        response = self.client.get(reverse("profile", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, 404)

    def test_profile_no_pk_unauthenticated_redirects_to_login(self):
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))

    def test_profile_no_pk_authenticated_shows_own(self):
        user = make_active_user()
        self.client.force_login(user)
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile_user"], user)


class EditProfileViewTests(TestCase):
    def test_get_requires_login(self):
        response = self.client.get(reverse("edit_profile"))
        self.assertEqual(response.status_code, 302)

    def test_get_authenticated_renders(self):
        user = make_active_user()
        self.client.force_login(user)
        response = self.client.get(reverse("edit_profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/edit_profile.html")
        self.assertContains(response, 'name="biography"')
        self.assertNotContains(response, 'name="digest_frequency"')
        self.assertNotContains(response, 'name="email"')

    def test_post_updates_profile_and_crops_avatar(self):
        user = make_active_user()
        self.client.force_login(user)
        response = self.client.post(reverse("edit_profile"), {
            "position": "Professor",
            "country_code": "US",
            "department": "Cornell",
            "website": "https://example.com",
            "biography": "A short biography.",
            "research_interests_input": '[{"value":"Economics"}]',
            "avatar": make_image_file(),
        })
        self.assertRedirects(response, reverse("profile"))
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.position, "Professor")
        self.assertEqual(user.profile.research_interests, ["Economics"])
        self.assertTrue(user.profile.avatar)

    def test_post_without_digest_frequency_defaults_off(self):
        user = make_active_user()
        self.client.force_login(user)
        response = self.client.post(reverse("edit_profile"), {
            "position": "Professor",
            "country_code": "US",
            "department": "Cornell",
            "website": "https://example.com",
            "biography": "A short biography.",
            "research_interests_input": '[{"value":"Economics"}]',
            "avatar": make_image_file(),
        })
        self.assertRedirects(response, reverse("profile"))
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.position, "Professor")


class SettingsViewTests(TestCase):
    def test_get_requires_login(self):
        response = self.client.get(reverse("settings"))
        self.assertEqual(response.status_code, 302)

    def test_get_authenticated_renders(self):
        user = make_active_user()
        self.client.force_login(user)
        response = self.client.get(reverse("settings"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/settings.html")
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="digest_frequency"')
        self.assertContains(response, reverse("password_change"))

    def test_post_save_account_updates_email(self):
        user = make_active_user(email="old@example.com")
        self.client.force_login(user)
        response = self.client.post(reverse("settings"), {
            "save_account": "1",
            "email": "new@example.com",
        })
        self.assertRedirects(response, reverse("settings") + "?saved=account")
        user.refresh_from_db()
        self.assertEqual(user.email, "new@example.com")

    def test_post_save_notifications_updates_digest(self):
        user = make_active_user()
        self.client.force_login(user)
        response = self.client.post(reverse("settings"), {
            "save_notifications": "1",
            "digest_frequency": "weekly",
        })
        self.assertRedirects(
            response, reverse("settings") + "?saved=notifications")
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.digest_frequency, "weekly")

    def test_post_save_notifications_without_frequency_defaults_off(self):
        user = make_active_user()
        user.profile.digest_frequency = "weekly"
        user.profile.save(update_fields=["digest_frequency"])
        self.client.force_login(user)
        response = self.client.post(reverse("settings"), {
            "save_notifications": "1",
        })
        self.assertRedirects(
            response, reverse("settings") + "?saved=notifications")
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.digest_frequency, "off")


class AdminLinkNavTests(TestCase):
    def test_admin_link_hidden_for_regular_user(self):
        user = make_active_user()
        self.client.force_login(user)
        response = self.client.get(reverse("settings"))
        self.assertNotContains(response, 'href="/admin/"')

    def test_admin_link_visible_for_staff(self):
        user = make_active_user(email="staff@example.com")
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        self.client.force_login(user)
        response = self.client.get(reverse("settings"))
        self.assertContains(response, 'href="/admin/"')


class LoginUrlSettingTests(TestCase):
    """Guard against LOGIN_URL drifting away from the real login route.

    A hardcoded LOGIN_URL that no longer matches accounts/urls.py sends every
    @login_required / LoginRequiredMixin redirect to a 404 instead of the login
    page, which is silent until a logged-out user clicks a protected link.
    """

    def test_login_url_resolves_to_the_login_view(self):
        from django.conf import settings
        from django.urls import resolve

        match = resolve(str(settings.LOGIN_URL))
        self.assertEqual(match.url_name, "login")

    def test_login_required_view_redirects_to_a_page_that_exists(self):
        response = self.client.get(reverse("settings"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")


class ProfileVisitsTests(TestCase):
    """Visits a member posted appear on their profile (Seminar.posted_by)."""

    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        from seminars.models import Seminar

        self.Seminar = Seminar
        self.owner = make_active_user("owner@example.com")
        self.other = make_active_user("other@example.com")
        self.today = timezone.localdate()
        self.delta = timedelta

    def _visit(self, user, status, university_name="Test University"):
        return self.Seminar.objects.create(
            posted_by=user,
            visitor_name="Visitor",
            visitor_email="visitor@example.com",
            university_name=university_name,
            visit_start=self.today + self.delta(days=10),
            visit_end=self.today + self.delta(days=20),
            status=status,
        )

    def _profile(self, user):
        return self.client.get(reverse("profile", kwargs={"pk": user.pk}))

    def test_approved_visit_shows_on_the_posters_profile(self):
        self._visit(self.owner, "approved", "Approved University")
        self.assertContains(self._profile(self.owner), "Approved University")

    def test_visit_does_not_show_on_someone_elses_profile(self):
        self._visit(self.owner, "approved", "Approved University")
        self.assertNotContains(self._profile(self.other), "Approved University")

    def test_pending_visit_is_hidden_from_other_viewers(self):
        self._visit(self.owner, "pending", "Secret University")
        self.assertNotContains(self._profile(self.owner), "Secret University")

    def test_owner_sees_their_own_pending_visit_flagged(self):
        self._visit(self.owner, "pending", "Secret University")
        self.client.force_login(self.owner)
        response = self._profile(self.owner)
        self.assertContains(response, "Secret University")
        self.assertContains(response, "Pending review")

    def test_rejected_visit_is_hidden_even_from_the_owner(self):
        self._visit(self.owner, "rejected", "Rejected University")
        self.client.force_login(self.owner)
        self.assertNotContains(self._profile(self.owner), "Rejected University")

    def test_member_with_no_visits_gets_an_empty_state(self):
        self.assertContains(self._profile(self.owner), "No visits posted yet.")

    def test_visits_section_precedes_discussion_papers(self):
        body = self._profile(self.owner).content.decode()
        self.assertLess(body.index("<h3>Visits</h3>"),
                        body.index("Labor Hub Discussion Papers"))


class ProfilePublicationVisibilityTests(TestCase):
    """A pending paper must not leak to the public via its author's profile."""

    def setUp(self):
        from publications.models import Author, Publication

        self.Publication = Publication
        self.owner = make_active_user("owner@example.com")
        self.author = Author.objects.create(user=self.owner, name="")

    def _paper(self, status, title):
        paper = self.Publication.objects.create(
            title=title, abstract="a", study_url="https://example.com", status=status,
        )
        paper.authors.set([self.author])
        return paper

    def _profile(self):
        return self.client.get(reverse("profile", kwargs={"pk": self.owner.pk}))

    def test_approved_paper_is_public(self):
        self._paper("approved", "Approved Paper")
        self.assertContains(self._profile(), "Approved Paper")

    def test_pending_paper_is_hidden_from_the_public(self):
        self._paper("pending", "Unapproved Paper")
        self.assertNotContains(self._profile(), "Unapproved Paper")

    def test_owner_still_sees_their_own_pending_paper(self):
        self._paper("pending", "Unapproved Paper")
        self.client.force_login(self.owner)
        self.assertContains(self._profile(), "Unapproved Paper")


class ProfilePublicationsEmptyStateTests(TestCase):
    """A member with no papers must see a message, not a silent blank gap.

    The Visits section has always shown one; the Discussion Papers section had no
    {% empty %} clause at all, so it rendered a heading followed by nothing.
    """

    def test_member_with_no_papers_gets_an_empty_state(self):
        user = make_active_user("nopapers@example.com")
        response = self.client.get(reverse("profile", kwargs={"pk": user.pk}))
        self.assertContains(response, "No discussion papers posted yet.")

    def test_empty_state_disappears_once_a_paper_exists(self):
        from publications.models import Author, Publication

        user = make_active_user("haspapers@example.com")
        author = Author.objects.create(user=user, name="")
        paper = Publication.objects.create(
            title="A Real Paper", abstract="a",
            study_url="https://example.com", status="approved",
        )
        paper.authors.set([author])
        response = self.client.get(reverse("profile", kwargs={"pk": user.pk}))
        self.assertContains(response, "A Real Paper")
        self.assertNotContains(response, "No discussion papers posted yet.")


class ProfileVisitCardDetailTests(TestCase):
    """The profile now uses the detailed visit card, not the minimal one.

    Detailed means the same card the Visits listing renders: "Visiting <uni>",
    the affiliation line and country pills -- none of which the minimal card
    showed. The heading differs by design (university, not visitor name), since
    the member's own name is already at the top of their profile.
    """

    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        from seminars.models import Seminar

        self.owner = make_active_user("owner@example.com")
        today = timezone.localdate()
        self.visit = Seminar.objects.create(
            posted_by=self.owner,
            visitor_name="Ada Lovelace",
            visitor_email="ada@example.com",
            visitor_affiliation="Analytical Engine Institute",
            university_name="Cornell University",
            countries=["US"],
            visit_start=today + timedelta(days=10),
            visit_end=today + timedelta(days=20),
            status="approved",
        )

    def _profile(self):
        return self.client.get(reverse("profile", kwargs={"pk": self.owner.pk}))

    def test_shows_the_detailed_fields(self):
        response = self._profile()
        self.assertContains(response, "Visiting Cornell University")
        self.assertContains(response, "Analytical Engine Institute")
        self.assertContains(response, "United States")

    def test_titles_the_card_by_university_not_visitor_name(self):
        response = self._profile()
        self.assertContains(response, 'class="card-title">Cornell University')

    def test_uses_the_detailed_card_not_the_minimal_one(self):
        """The minimal card renders an h6/card-surface pair with no card-title."""
        response = self._profile()
        self.assertContains(response, "card-title")


class VisitsListTitleTests(TestCase):
    """The title override must not leak from the profile onto the listing."""

    def test_list_page_still_titles_cards_by_visitor_name(self):
        from datetime import timedelta

        from django.utils import timezone

        from seminars.models import Seminar

        today = timezone.localdate()
        Seminar.objects.create(
            visitor_name="Ada Lovelace",
            visitor_email="ada@example.com",
            university_name="Cornell University",
            visit_start=today + timedelta(days=10),
            visit_end=today + timedelta(days=20),
            status="approved",
        )
        response = self.client.get(reverse("seminars-list"))
        self.assertContains(response, 'class="card-title">Ada Lovelace')
