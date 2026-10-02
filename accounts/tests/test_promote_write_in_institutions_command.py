from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import CustomUser
from seminars.models import University


def make_user(email, university_name="", country_code="US"):
    user = CustomUser.objects.create_user(
        email=email, password="pass12345",
        first_name="First", last_name="Last", is_active=True,
    )
    user.profile.university_name = university_name
    user.profile.country_code = country_code
    user.profile.save()
    return user


class PromoteWriteInInstitutionsCommandTests(TestCase):
    def test_dry_run_reports_without_writing(self):
        user = make_user("a@example.com", university_name="New College")
        out = StringIO()
        call_command("promote_write_in_institutions", stdout=out)

        user.refresh_from_db()
        self.assertEqual(user.profile.university_name, "New College")
        self.assertIsNone(user.profile.university)
        self.assertFalse(University.objects.filter(name="New College").exists())
        self.assertIn("New College", out.getvalue())

    def test_apply_creates_and_links_university(self):
        user = make_user("b@example.com", university_name="New College")
        call_command("promote_write_in_institutions", "--apply", stdout=StringIO())

        user.refresh_from_db()
        self.assertEqual(user.profile.university_name, "")
        self.assertEqual(user.profile.university.name, "New College")

    def test_apply_reuses_an_existing_university(self):
        existing = University.objects.create(
            name="Existing College", country_code="US", source="import")
        user = make_user("c@example.com", university_name="existing college")
        call_command("promote_write_in_institutions", "--apply", stdout=StringIO())

        user.refresh_from_db()
        self.assertEqual(user.profile.university, existing)
        self.assertEqual(University.objects.filter(name__iexact="existing college").count(), 1)

    def test_profiles_with_no_write_in_are_left_alone(self):
        user = make_user("d@example.com", university_name="")
        call_command("promote_write_in_institutions", "--apply", stdout=StringIO())
        user.refresh_from_db()
        self.assertIsNone(user.profile.university)

    def test_profiles_with_no_country_are_left_alone(self):
        user = make_user("e@example.com", university_name="Some College", country_code="")
        call_command("promote_write_in_institutions", "--apply", stdout=StringIO())
        user.refresh_from_db()
        self.assertEqual(user.profile.university_name, "Some College")
        self.assertIsNone(user.profile.university)

    def test_profiles_with_a_picked_university_are_left_alone(self):
        picked = University.objects.create(
            name="Already Picked", country_code="US", source="import")
        user = make_user("f@example.com", university_name="Irrelevant")
        user.profile.university = picked
        user.profile.save()
        call_command("promote_write_in_institutions", "--apply", stdout=StringIO())
        user.refresh_from_db()
        self.assertEqual(user.profile.university, picked)
        self.assertEqual(user.profile.university_name, "Irrelevant")
