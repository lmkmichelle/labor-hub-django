"""The university picker must not render every University as an <option>.

The table holds ~10k rows; emitting them all on each page load exhausted the
app container's memory (gunicorn workers SIGKILLed -> 502s on edit-profile,
the application forms and the admin). The picker JS refills the list per
country, so the server renders only the saved selection but must still
*validate* against every university.
"""
from django.test import TestCase
from django.urls import reverse

from accounts.forms import UpdateProfileForm
from accounts.models import CustomUser
from seminars.forms import SeminarForm
from seminars.models import University


def seed_universities(count=60):
    return University.objects.bulk_create([
        University(name=f"Zzuni {i:03d} University", country_code="DE")
        for i in range(count)
    ])


class UniversityChoiceFieldTests(TestCase):
    def setUp(self):
        seed_universities()
        self.saved = University.objects.create(name="Saved Institute", country_code="US")

    def _option_count(self, form):
        return len(list(form.fields["university"].choices))

    def test_unbound_form_renders_only_the_empty_choice(self):
        self.assertEqual(self._option_count(SeminarForm()), 1)

    def test_saved_selection_is_the_only_extra_option(self):
        form = SeminarForm(initial={"university": self.saved.pk})
        names = [label for _, label in form.fields["university"].choices]
        self.assertEqual(len(names), 2)
        self.assertIn("Saved Institute (United States)", names[1])

    def test_bound_form_renders_only_the_submitted_option(self):
        form = SeminarForm(data={"university": str(self.saved.pk)})
        self.assertEqual(self._option_count(form), 2)

    def test_any_university_still_validates(self):
        far = University.objects.filter(country_code="DE").last()
        form = SeminarForm(data={
            "country_code": "DE", "university": far.pk, "visit_type": "open",
            "visit_start": "2030-01-01",
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["university"], far)

    def test_unknown_university_is_rejected(self):
        form = SeminarForm(data={
            "country_code": "DE", "university": 999999, "visit_type": "open",
            "visit_start": "2030-01-01",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("university", form.errors)

    def test_profile_form_renders_only_the_saved_university(self):
        user = CustomUser.objects.create_user(
            email="u@example.com", password="x", is_active=True)
        user.profile.university = self.saved
        user.profile.save()
        form = UpdateProfileForm(instance=user.profile)
        self.assertEqual(self._option_count(form), 2)


class UniversityPickerPagesTests(TestCase):
    def setUp(self):
        seed_universities()
        self.saved = University.objects.create(name="Saved Institute", country_code="US")
        self.user = CustomUser.objects.create_user(
            email="u@example.com", password="x", first_name="U", last_name="V",
            role=CustomUser.Role.RESEARCHER, is_active=True)

    def test_pages_do_not_list_every_university(self):
        self.client.force_login(self.user)
        for name in ("edit_profile", "apply_researcher", "apply_student", "seminar-create"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "Zzuni 0")

    def test_edit_profile_keeps_the_saved_affiliation_selected(self):
        self.user.profile.university = self.saved
        self.user.profile.save()
        self.client.force_login(self.user)
        response = self.client.get(reverse("edit_profile"))
        self.assertContains(
            response, f'<option value="{self.saved.pk}" selected>')

    def test_admin_application_change_page_has_no_university_dump(self):
        from accounts.models import UserApplication
        admin = CustomUser.objects.create_superuser(
            email="a@example.com", password="x")
        app = UserApplication.objects.create(
            email="app@example.com", first_name="A", last_name="B",
            role=CustomUser.Role.RESEARCHER, country_code="US",
            university=self.saved, password="x")
        self.client.force_login(admin)
        response = self.client.get(
            reverse("admin:accounts_userapplication_change", args=[app.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Zzuni 0")
