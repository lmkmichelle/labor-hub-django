import io
import os
import shutil
import tempfile
import time
from unittest import mock

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import CustomUser
from publications.models import Publication


def run(*args):
    out = io.StringIO()
    call_command("reclaim_media", *args, stdout=out)
    return out.getvalue()


class ReclaimMediaTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="laborhub-reclaim-")
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)

        # One referenced file of each kind the site stores...
        self.paper = Publication.objects.create(title="T", abstract="a", status="approved")
        self.paper.pdf.save("kept.pdf", ContentFile(b"%PDF kept"), save=True)
        self.user = CustomUser.objects.create_user(
            email="u@example.com", password="x", first_name="U", last_name="V", is_active=True)
        self.user.profile.cv_file.save("cv.pdf", ContentFile(b"%PDF cv"), save=True)

    def orphan(self, relative, size=2048, age_hours=72):
        path = os.path.join(self.media, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(b"x" * size)
        stamp = time.time() - age_hours * 3600
        os.utime(path, (stamp, stamp))
        return path

    def test_dry_run_lists_orphans_and_deletes_nothing(self):
        old_copy = self.orphan("publications/pdf/DP3-old.pdf")
        out = run()
        self.assertIn("DP3-old.pdf", out)
        self.assertIn("Total reclaimable: 1 files", out)
        self.assertIn("Dry run: nothing was deleted", out)
        self.assertTrue(os.path.exists(old_copy))

    def test_files_the_database_uses_are_never_listed_or_deleted(self):
        self.orphan("publications/pdf/orphan.pdf")
        out = run("--apply")
        self.assertNotIn("kept.pdf", out)
        self.assertNotIn("cv.pdf", out)
        self.assertTrue(self.paper.pdf.storage.exists(self.paper.pdf.name))
        self.assertTrue(self.user.profile.cv_file.storage.exists(self.user.profile.cv_file.name))

    def test_apply_deletes_only_old_unreferenced_files(self):
        old = self.orphan("research_papers/old.pdf", age_hours=72)
        fresh = self.orphan("research_papers/uploading-now.pdf", age_hours=0.1)
        out = run("--apply")
        self.assertIn("Deleted 1 files", out)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(fresh))  # too new: could be mid-save
        self.assertIn("newer than 24h (left alone): 1 files", out)

    def test_min_age_can_be_changed(self):
        recent = self.orphan("research_papers/two-hours-old.pdf", age_hours=2)
        self.assertIn("Total reclaimable: 0 files", run())
        self.assertIn("Total reclaimable: 1 files", run("--min-age-hours", "1"))
        self.assertTrue(os.path.exists(recent))

    def test_summary_groups_by_folder_with_sizes(self):
        self.orphan("publications/pdf/a.pdf", size=3 * 1024 * 1024)
        self.orphan("loose-cv.pdf", size=1024 * 1024)
        out = run()
        self.assertIn("publications/pdf/  1 files, 3.0 MB", out)
        self.assertIn("(media root)/  1 files, 1.0 MB", out)
        self.assertIn("Total reclaimable: 2 files, 4.0 MB", out)

    def test_refuses_non_filesystem_storage(self):
        with mock.patch("core.management.commands.reclaim_media.default_storage", object()):
            with self.assertRaises(CommandError):
                run()
