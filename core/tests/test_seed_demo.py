"""Tests for the ``seed_demo`` management command.

The command is intended for local development, so these tests focus on its
contract: it creates the expected demo data, is idempotent (no duplicates on a
second run), guards against running in production (``DEBUG=False``), and
``--reset`` removes only the demo data it created.

The project test settings (``nole.settings_test``) run with ``DEBUG=False``, so
the data-oriented tests pass ``force=True`` to bypass the production guard.
"""

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import CustomUser, Profile
from events.models import Event
from jobs.models import Job
from publications.models import Publication
from seminars.models import Seminar, University

DEMO_SUFFIX = "@laborhub.demo"


def run_seed(**kwargs):
    kwargs.setdefault("force", True)
    call_command("seed_demo", stdout=StringIO(), stderr=StringIO(), **kwargs)


class SeedDemoDataTests(TestCase):
    def test_creates_expected_demo_data(self):
        run_seed()

        self.assertEqual(
            CustomUser.objects.filter(email__endswith=DEMO_SUFFIX).count(), 5
        )
        self.assertEqual(
            Profile.objects.filter(user__email__endswith=DEMO_SUFFIX).count(), 5
        )
        self.assertEqual(Publication.objects.count(), 5)
        self.assertEqual(Event.objects.count(), 4)
        self.assertEqual(University.objects.filter(source="demo").count(), 4)
        self.assertEqual(
            Seminar.objects.filter(visitor_email__endswith=DEMO_SUFFIX).count(), 3
        )
        self.assertEqual(Job.objects.count(), 5)

    def test_demo_users_can_authenticate(self):
        """Passwords are hashed properly, so demo logins actually work."""
        run_seed()
        admin = CustomUser.objects.get(email="admin@laborhub.demo")
        self.assertTrue(admin.check_password("demo12345"))
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)

    def test_custom_password(self):
        run_seed(password="s3cret-demo")
        user = CustomUser.objects.get(email="rosa.researcher@laborhub.demo")
        self.assertTrue(user.check_password("s3cret-demo"))

    def test_students_are_linked_to_an_advisor(self):
        run_seed()
        students = CustomUser.objects.filter(role=CustomUser.Role.STUDENT)
        self.assertEqual(students.count(), 2)
        for student in students:
            self.assertIsNotNone(student.advisor)
            self.assertEqual(student.advisor.role, CustomUser.Role.RESEARCHER)

    def test_home_page_relevant_data_is_visible(self):
        """Seeded content matches the filters the home view applies."""
        run_seed()
        # Publications are approved so they show in "recent papers".
        self.assertEqual(Publication.objects.filter(status="approved").count(), 5)
        # Events are approved and dated in the future.
        self.assertEqual(Event.objects.filter(status="approved").count(), 4)
        # Publications carry authors (both user-linked and external).
        self.assertTrue(all(p.authors.exists() for p in Publication.objects.all()))


class SeedDemoIdempotencyTests(TestCase):
    def test_running_twice_does_not_duplicate(self):
        run_seed()
        run_seed()

        self.assertEqual(
            CustomUser.objects.filter(email__endswith=DEMO_SUFFIX).count(), 5
        )
        self.assertEqual(Publication.objects.count(), 5)
        self.assertEqual(Event.objects.count(), 4)
        self.assertEqual(Job.objects.count(), 5)
        self.assertEqual(
            Seminar.objects.filter(visitor_email__endswith=DEMO_SUFFIX).count(), 3
        )
        # A second run must not create a duplicate Profile for any user (the
        # OneToOne would raise) nor duplicate universities.
        self.assertEqual(
            Profile.objects.filter(user__email__endswith=DEMO_SUFFIX).count(), 5
        )
        self.assertEqual(University.objects.filter(source="demo").count(), 4)


class SeedDemoResetTests(TestCase):
    def test_reset_removes_and_recreates_demo_data(self):
        run_seed()
        run_seed(reset=True)

        self.assertEqual(
            CustomUser.objects.filter(email__endswith=DEMO_SUFFIX).count(), 5
        )
        self.assertEqual(Job.objects.count(), 5)

    def test_reset_preserves_non_demo_data(self):
        real_user = CustomUser.objects.create_user(
            email="real.person@example.com",
            password="realpass123",
            first_name="Real",
            last_name="Person",
            is_active=True,
        )
        real_job = Job.objects.create(
            title="A genuine non-demo job",
            description="Not created by seed_demo.",
            url="https://example.com/real",
            deadline="2099-01-01",
        )

        run_seed(reset=True)

        self.assertTrue(
            CustomUser.objects.filter(pk=real_user.pk).exists(),
            "seed_demo --reset must not delete real users",
        )
        self.assertTrue(
            Job.objects.filter(pk=real_job.pk).exists(),
            "seed_demo --reset must not delete real jobs",
        )


class SeedDemoGuardTests(TestCase):
    def test_refuses_to_run_when_debug_is_false(self):
        # settings_test runs with DEBUG=False, so no override is needed.
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO(), stderr=StringIO())
        self.assertEqual(CustomUser.objects.filter(email__endswith=DEMO_SUFFIX).count(), 0)

    def test_force_overrides_the_guard(self):
        call_command("seed_demo", force=True, stdout=StringIO(), stderr=StringIO())
        self.assertEqual(CustomUser.objects.filter(email__endswith=DEMO_SUFFIX).count(), 5)

    @override_settings(DEBUG=True)
    def test_runs_without_force_when_debug_is_true(self):
        call_command("seed_demo", stdout=StringIO(), stderr=StringIO())
        self.assertEqual(CustomUser.objects.filter(email__endswith=DEMO_SUFFIX).count(), 5)
