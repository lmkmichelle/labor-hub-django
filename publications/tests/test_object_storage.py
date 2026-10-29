import io
import os
import tempfile
from unittest import mock

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from storages.backends.s3 import S3Storage

from accounts.models import CustomUser
from core.storage import PaperBucketStorage, paper_storage
from publications.models import Publication
from publications.tests.test_models import make_publication


def bucket_storage():
    return PaperBucketStorage(bucket_name="laborhub", access_key="k", secret_key="s",
                              endpoint_url="http://object-storage.internal:8080")


class FakeBucket(PaperBucketStorage):
    """A bucket held in a dict, for the copy command."""

    def __init__(self):
        super().__init__(bucket_name="laborhub", access_key="k", secret_key="s")
        self.objects = {}

    def exists(self, name):
        return name in self.objects

    def size(self, name):
        return len(self.objects[name])

    def save(self, name, content, max_length=None):
        self.objects[name] = content.read()
        return name


class PaperBucketStorageTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="laborhub-papers-")
        os.makedirs(os.path.join(self.media, "publications/pdf"))
        with open(os.path.join(self.media, "publications/pdf/old.pdf"), "wb") as f:
            f.write(b"on the disk")
        patcher = override_settings(MEDIA_ROOT=self.media)
        patcher.enable()
        self.addCleanup(patcher.disable)

    def test_paper_only_on_the_disk_is_still_readable(self):
        with mock.patch.object(S3Storage, "exists", return_value=False):
            with bucket_storage().open("publications/pdf/old.pdf") as f:
                self.assertEqual(f.read(), b"on the disk")
            self.assertEqual(bucket_storage().size("publications/pdf/old.pdf"), 11)

    def test_paper_in_the_bucket_is_read_from_the_bucket(self):
        with mock.patch.object(S3Storage, "exists", return_value=True), \
                mock.patch.object(S3Storage, "_open",
                                  return_value=ContentFile(b"in the bucket")) as s3_open:
            f = bucket_storage()._open("publications/pdf/old.pdf")
        s3_open.assert_called_once()
        self.assertEqual(f.read(), b"in the bucket")

    def test_delete_removes_both_copies(self):
        with mock.patch.object(S3Storage, "delete") as s3_delete:
            bucket_storage().delete("publications/pdf/old.pdf")
        s3_delete.assert_called_once_with("publications/pdf/old.pdf")
        self.assertFalse(os.path.exists(os.path.join(self.media, "publications/pdf/old.pdf")))

    def test_url_is_the_staff_view_not_the_internal_bucket(self):
        self.assertEqual(
            bucket_storage().url("publications/pdf/a.pdf"),
            reverse("publication_file", args=["publications/pdf/a.pdf"]))


class PublicationFileViewTests(TestCase):
    def setUp(self):
        self.pub = make_publication()
        self.pub.pdf.save("a.pdf", ContentFile(b"%PDF-1.4 covered"), save=True)
        self.url = reverse("publication_file", args=[self.pub.pdf.name])

    def _login(self, **extra):
        user = CustomUser.objects.create_user(
            email="u@example.com", password="pass12345", is_active=True, **extra)
        self.client.force_login(user)

    def test_staff_can_open_a_paper_file(self):
        self._login(is_staff=True)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4 covered")

    def test_non_staff_and_anonymous_are_turned_away(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self._login()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_staff_can_open_an_application_sample(self):
        from accounts.models import ResearchPaper, UserApplication
        application = UserApplication.objects.create(
            email="a@example.com", first_name="A", last_name="B", password="x")
        sample = ResearchPaper.objects.create(
            application=application, paper=ContentFile(b"%PDF-1.4 sample", name="s.pdf"))
        self._login(is_staff=True)
        response = self.client.get(reverse("publication_file", args=[sample.paper.name]))
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4 sample")

    def test_only_names_a_paper_holds_are_served(self):
        self._login(is_staff=True)
        response = self.client.get(
            reverse("publication_file", args=["accounts/secret.txt"]))
        self.assertEqual(response.status_code, 404)


class MovePapersToBucketTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="laborhub-papers-")
        patcher = override_settings(MEDIA_ROOT=self.media)
        patcher.enable()
        self.addCleanup(patcher.disable)
        self.pub = make_publication()
        path = os.path.join(self.media, "publications/pdf")
        os.makedirs(path)
        with open(os.path.join(path, "a.pdf"), "wb") as f:
            f.write(b"%PDF-1.4 a")
        Publication.objects.filter(pk=self.pub.pk).update(pdf="publications/pdf/a.pdf")
        self.bucket = FakeBucket()

    def run_command(self, *args):
        with mock.patch(
                "publications.management.commands.move_papers_to_bucket.paper_storage",
                return_value=self.bucket):
            call_command("move_papers_to_bucket", *args, stdout=io.StringIO())

    def test_copies_under_the_same_name_and_keeps_the_disk_copy(self):
        self.run_command()
        self.assertEqual(self.bucket.objects, {"publications/pdf/a.pdf": b"%PDF-1.4 a"})
        self.assertTrue(os.path.exists(os.path.join(self.media, "publications/pdf/a.pdf")))

    def test_application_samples_are_copied_too(self):
        from django.core.files.base import ContentFile as CF
        from accounts.models import ResearchPaper, UserApplication
        application = UserApplication.objects.create(
            email="a@example.com", first_name="A", last_name="B", password="x")
        sample = ResearchPaper.objects.create(
            application=application, paper=CF(b"%PDF-1.4 s", name="s.pdf"))
        self.run_command()
        self.assertIn(sample.paper.name, self.bucket.objects)

    def test_delete_local_frees_the_disk_after_copying(self):
        self.run_command("--delete-local")
        self.assertIn("publications/pdf/a.pdf", self.bucket.objects)
        self.assertFalse(os.path.exists(os.path.join(self.media, "publications/pdf/a.pdf")))

    def test_dry_run_changes_nothing(self):
        self.run_command("--dry-run", "--delete-local")
        self.assertEqual(self.bucket.objects, {})
        self.assertTrue(os.path.exists(os.path.join(self.media, "publications/pdf/a.pdf")))

    def test_refuses_when_papers_are_not_on_object_storage(self):
        self.assertNotIsInstance(paper_storage(), PaperBucketStorage)
        with self.assertRaises(CommandError):
            call_command("move_papers_to_bucket", stdout=io.StringIO())
