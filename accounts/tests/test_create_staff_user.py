from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from accounts.management.commands.create_staff_user import generate_password, parse_person
from accounts.models import CustomUser, Profile


def run(*args, **kwargs):
    out = StringIO()
    call_command("create_staff_user", *args, stdout=out, stderr=out, **kwargs)
    return out.getvalue()


class ParsePersonTests(TestCase):
    def test_splits_name_and_address(self):
        self.assertEqual(
            parse_person("Ada Lovelace <ada@example.edu>"),
            ("Ada", "Lovelace", "ada@example.edu"),
        )

    def test_multi_word_surname_stays_together(self):
        self.assertEqual(
            parse_person("Jean de la Fontaine <jean@example.edu>"),
            ("Jean", "de la Fontaine", "jean@example.edu"),
        )

    def test_rejects_missing_name(self):
        with self.assertRaises(CommandError):
            parse_person("ada@example.edu")

    def test_rejects_missing_address(self):
        with self.assertRaises(CommandError):
            parse_person("Ada Lovelace")


class GeneratePasswordTests(TestCase):
    def test_respects_requested_length_and_is_random(self):
        first = generate_password(24)
        second = generate_password(24)
        self.assertEqual(len(first), 24)
        self.assertNotEqual(first, second)

    def test_excludes_ambiguous_characters(self):
        for _ in range(20):
            self.assertFalse(set(generate_password()) & set("0O1lI"))


class CreateStaffUserCommandTests(TestCase):
    def test_creates_superuser_researcher_with_profile(self):
        output = run("Ada Lovelace <ada@example.edu>", "--superuser")

        user = CustomUser.objects.get(email="ada@example.edu")
        self.assertEqual(user.first_name, "Ada")
        self.assertEqual(user.last_name, "Lovelace")
        self.assertEqual(user.role, CustomUser.Role.RESEARCHER)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_active)
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertIn("ada@example.edu", output)

    def test_printed_password_actually_authenticates(self):
        output = run("Ada Lovelace <ada@example.edu>", "--superuser")

        password = next(
            line.split()[1] for line in output.splitlines() if "ada@example.edu" in line
        )
        user = CustomUser.objects.get(email="ada@example.edu")
        self.assertTrue(user.check_password(password))

    def test_creates_several_people_at_once(self):
        run(
            "Ada Lovelace <ada@example.edu>",
            "Alan Turing <alan@example.edu>",
            "--superuser",
        )
        self.assertEqual(CustomUser.objects.count(), 2)

    def test_researcher_role_keeps_account_in_public_directory(self):
        run("Ada Lovelace <ada@example.edu>", "--superuser")
        directory = CustomUser.objects.filter(
            is_active=True,
            role__in=(CustomUser.Role.STUDENT, CustomUser.Role.RESEARCHER),
        )
        self.assertEqual([u.email for u in directory], ["ada@example.edu"])

    def test_country_lands_on_profile(self):
        run("Ada Lovelace <ada@example.edu>", "--superuser", "--country", "us")
        self.assertEqual(
            Profile.objects.get(user__email="ada@example.edu").country_code, "US"
        )

    def test_rejects_unknown_country(self):
        with self.assertRaises(CommandError):
            run("Ada Lovelace <ada@example.edu>", "--country", "ZZZ")
        self.assertFalse(CustomUser.objects.exists())

    def test_non_superuser_is_still_active(self):
        run("Ada Lovelace <ada@example.edu>")
        user = CustomUser.objects.get(email="ada@example.edu")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_superuser)

    def test_no_password_creates_unusable_password(self):
        run("Ada Lovelace <ada@example.edu>", "--superuser", "--no-password")
        user = CustomUser.objects.get(email="ada@example.edu")
        self.assertFalse(user.has_usable_password())

    def test_rerun_leaves_existing_password_untouched(self):
        run("Ada Lovelace <ada@example.edu>", "--superuser")
        user = CustomUser.objects.get(email="ada@example.edu")
        user.set_password("chosen-by-the-user")
        user.save()

        output = run("Ada Lovelace <ada@example.edu>", "--superuser")

        user.refresh_from_db()
        self.assertTrue(user.check_password("chosen-by-the-user"))
        self.assertIn("already exists", output)
        self.assertEqual(CustomUser.objects.count(), 1)

    def test_reset_existing_issues_a_new_password(self):
        run("Ada Lovelace <ada@example.edu>", "--superuser")
        user = CustomUser.objects.get(email="ada@example.edu")
        user.set_password("chosen-by-the-user")
        user.save()

        run("Ada Lovelace <ada@example.edu>", "--superuser", "--reset-existing")

        user.refresh_from_db()
        self.assertFalse(user.check_password("chosen-by-the-user"))

    def test_a_bad_spec_creates_nobody(self):
        with self.assertRaises(CommandError):
            run("Ada Lovelace <ada@example.edu>", "not-a-valid-spec", "--superuser")
        self.assertFalse(CustomUser.objects.exists())
