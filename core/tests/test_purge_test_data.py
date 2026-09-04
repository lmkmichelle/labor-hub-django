from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from accounts.models import CustomUser
from jobs.models import Job


def run(*args):
    out = StringIO()
    call_command("purge_test_data", *args, stdout=out, stderr=out)
    return out.getvalue()


def make_user(email, **extra):
    return CustomUser.objects.create_user(
        email=email, password="x", first_name="T", last_name="U",
        is_active=True, **extra,
    )


def make_job(uploader, title="Test Job"):
    return Job.objects.create(
        title=title, uploader=uploader, description="d", url="https://e.org",
        deadline="2099-01-01", countries=["US"], categories=["predoc"],
    )


class PurgeTestDataTests(TestCase):
    def test_no_ids_reports_and_deletes_nothing(self):
        user = make_user("keep@example.com")
        job = make_job(user)

        output = run()

        self.assertIn("keep@example.com", output)
        self.assertIn("Nothing deleted", output)
        self.assertTrue(CustomUser.objects.filter(pk=user.pk).exists())
        self.assertTrue(Job.objects.filter(pk=job.pk).exists())

    def test_ids_without_confirm_is_a_dry_run(self):
        user = make_user("dry@example.com")
        job = make_job(user)

        output = run("--job-ids", str(job.pk))

        self.assertIn("Would delete", output)
        self.assertTrue(Job.objects.filter(pk=job.pk).exists())

    def test_confirm_deletes_named_rows_only(self):
        victim = make_user("victim@example.com")
        bystander = make_user("bystander@example.com")
        victim_job = make_job(victim, title="Victim Job")
        bystander_job = make_job(bystander, title="Bystander Job")

        run("--user-ids", str(victim.pk),
            "--job-ids", str(victim_job.pk), "--confirm")

        self.assertFalse(CustomUser.objects.filter(pk=victim.pk).exists())
        self.assertFalse(Job.objects.filter(pk=victim_job.pk).exists())
        self.assertTrue(CustomUser.objects.filter(pk=bystander.pk).exists())
        self.assertTrue(Job.objects.filter(pk=bystander_job.pk).exists())

    def test_refuses_superuser_without_force(self):
        root = make_user("root@example.com", is_staff=True, is_superuser=True)
        with self.assertRaises(CommandError):
            run("--user-ids", str(root.pk), "--confirm")
        self.assertTrue(CustomUser.objects.filter(pk=root.pk).exists())

    def test_force_allows_superuser_deletion(self):
        root = make_user("root2@example.com", is_staff=True, is_superuser=True)
        run("--user-ids", str(root.pk), "--confirm", "--force")
        self.assertFalse(CustomUser.objects.filter(pk=root.pk).exists())

    def test_unknown_id_warns_and_continues(self):
        output = run("--job-ids", "999999")
        self.assertIn("No job with id 999999", output)
