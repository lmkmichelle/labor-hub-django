"""Position / Department / Affiliation on profiles and applications.

`education` (labelled "Current Institution" but holding degree history) became
`department`, and affiliation became a real University reference with a
free-text fallback -- the same FK + name pair Seminar already uses.
"""
from django.test import TestCase
from django.urls import reverse

from accounts.forms import UpdateProfileForm
from accounts.models import CustomUser, UserApplication
from seminars.models import University


def make_user(email="member@example.com", **profile_fields):
    user = CustomUser.objects.create_user(
        email=email, password="pass12345", first_name="Ada", last_name="Lovelace",
        is_active=True,
    )
    if profile_fields:
        for field, value in profile_fields.items():
            setattr(user.profile, field, value)
        user.profile.save()
    return user


class ProfileAffiliationTests(TestCase):
    def setUp(self):
        self.cornell = University.objects.create(name="Cornell University", country_code="US")

    def test_display_prefers_the_linked_university(self):
        user = make_user(university=self.cornell, university_name="Typed Instead")
        self.assertEqual(user.profile.get_university_display(), "Cornell University")

    def test_display_falls_back_to_the_typed_name(self):
        user = make_user(university_name="Some Small College")
        self.assertEqual(user.profile.get_university_display(), "Some Small College")

    def test_display_is_empty_when_neither_is_set(self):
        self.assertEqual(make_user().profile.get_university_display(), "")

    def test_deleting_a_university_does_not_delete_the_profile(self):
        user = make_user(university=self.cornell)
        self.cornell.delete()
        user.profile.refresh_from_db()
        self.assertIsNone(user.profile.university)
        self.assertTrue(CustomUser.objects.filter(pk=user.pk).exists())


class ProfileFormTests(TestCase):
    def test_form_exposes_the_new_fields_and_not_education(self):
        form = UpdateProfileForm()
        self.assertIn("department", form.fields)
        self.assertIn("university", form.fields)
        self.assertIn("university_name", form.fields)
        self.assertNotIn("education", form.fields)

    def test_labels_match_what_the_professors_asked_for(self):
        form = UpdateProfileForm()
        self.assertEqual(form.fields["department"].label, "Department")
        self.assertEqual(form.fields["position"].label, "Position")

    # NOTE: these assert on the university field specifically rather than on
    # form.is_valid(). UpdateProfileForm declares `avatar` and `website` without
    # required=False, so a bound form without them is invalid for reasons that
    # predate the affiliation work and are unrelated to it.
    def test_a_posted_university_is_accepted(self):
        """Regression: the queryset starts empty, so __init__ must widen it."""
        cornell = University.objects.create(name="Cornell University", country_code="US")
        user = make_user()
        form = UpdateProfileForm(
            data={
                "position": "Professor", "department": "Economics",
                "university": str(cornell.pk), "university_name": "",
                "country_code": "US", "biography": "Bio",
                "research_interests_input": "[]",
            },
            instance=user.profile,
        )
        form.is_valid()
        self.assertNotIn("university", form.errors)
        self.assertEqual(form.cleaned_data.get("university"), cornell)

    def test_affiliation_is_optional(self):
        user = make_user()
        form = UpdateProfileForm(
            data={
                "position": "Professor", "department": "Economics",
                "university": "", "university_name": "",
                "country_code": "US", "biography": "Bio",
                "research_interests_input": "[]",
            },
            instance=user.profile,
        )
        form.is_valid()
        self.assertNotIn("university", form.errors)
        self.assertNotIn("university_name", form.errors)


class ApplicationApprovalCarriesAffiliationTests(TestCase):
    """approve() copies the application's details onto the new profile."""

    def test_department_and_affiliation_reach_the_new_profile(self):
        cornell = University.objects.create(name="Cornell University", country_code="US")
        application = UserApplication.objects.create(
            email="new@example.com", first_name="New", last_name="Member",
            position="Postdoc", department="Economics", university=cornell,
            university_name="", password="hashed", country_code="US",
        )
        user = application.approve()
        self.assertEqual(user.profile.department, "Economics")
        self.assertEqual(user.profile.university, cornell)

    def test_typed_affiliation_reaches_the_new_profile(self):
        application = UserApplication.objects.create(
            email="new@example.com", first_name="New", last_name="Member",
            position="Postdoc", department="Economics",
            university_name="Small College", password="hashed", country_code="US",
        )
        user = application.approve()
        self.assertEqual(user.profile.get_university_display(), "Small College")


class ScholarSearchTests(TestCase):
    """The directory search must follow the renamed and new fields."""

    def setUp(self):
        self.cornell = University.objects.create(name="Cornell University", country_code="US")

    def _search(self, term):
        response = self.client.get(reverse("scholars"), {"q": term})
        return [u.email for u in response.context["users"]]

    def test_finds_by_department(self):
        make_user("econ@example.com", department="Econometrics")
        self.assertIn("econ@example.com", self._search("Econometrics"))

    def test_finds_by_linked_university_name(self):
        make_user("cornell@example.com", university=self.cornell)
        self.assertIn("cornell@example.com", self._search("Cornell"))

    def test_finds_by_typed_university_name(self):
        make_user("small@example.com", university_name="Small College")
        self.assertIn("small@example.com", self._search("Small College"))

    def test_does_not_match_unrelated_members(self):
        make_user("other@example.com", department="Sociology")
        self.assertNotIn("other@example.com", self._search("Econometrics"))


class ProfilePageTests(TestCase):
    def test_profile_shows_position_department_and_affiliation(self):
        cornell = University.objects.create(name="Cornell University", country_code="US")
        user = make_user(position="Professor", department="Economics", university=cornell)
        response = self.client.get(reverse("profile", kwargs={"pk": user.pk}))
        self.assertContains(response, "Professor")
        self.assertContains(response, "Economics")
        self.assertContains(response, "Cornell University")
