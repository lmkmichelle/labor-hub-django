"""Copy paper PDFs (discussion papers and application samples) from the app's disk into the object-storage bucket.

    python manage.py move_papers_to_bucket                  # copy, keep the disk copies
    python manage.py move_papers_to_bucket --delete-local   # copy, then free the disk

Run once after the deploy that enabled the bucket. Safe to re-run: a file already in
the bucket is skipped, and a disk copy is deleted only after the bucket copy is
confirmed to exist at the same size. Until it has run, downloads fall back to the
disk copy (core.storage.PaperBucketStorage), so nothing breaks in between.
"""
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.management.base import BaseCommand, CommandError

from accounts.models import ResearchPaper
from core.storage import PaperBucketStorage, paper_storage
from publications.models import Publication

MB = 1024 * 1024


class Command(BaseCommand):
    help = "Copy paper PDFs from the local disk into the object-storage bucket."

    def add_arguments(self, parser):
        parser.add_argument("--delete-local", action="store_true",
                            help="Delete each disk copy once it is safely in the bucket.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Only list what would be copied.")

    def handle(self, *args, **options):
        bucket = paper_storage()
        if not isinstance(bucket, PaperBucketStorage):
            raise CommandError(
                "Papers are not on object storage here (no OBJECT_STORAGE_* variables).")
        disk = FileSystemStorage(location=str(settings.MEDIA_ROOT))

        names = set()
        for pdf, original in Publication.objects.values_list("pdf", "pdf_original"):
            names.update(name for name in (pdf, original) if name)
        names.update(name for name in ResearchPaper.objects.values_list("paper", flat=True)
                     if name)

        copied = skipped = missing = freed = 0
        for name in sorted(names):
            on_bucket = bucket.exists(name)
            if not on_bucket and not disk.exists(name):
                missing += 1
                self.stderr.write(f"missing everywhere: {name}")
                continue
            if not on_bucket:
                size = disk.size(name)
                self.stdout.write(f"copy {size / MB:6.1f} MB  {name}")
                if options["dry_run"]:
                    continue
                with disk.open(name, "rb") as source:
                    # Save under the exact same name: the database already points at it.
                    bucket.file_overwrite = True
                    try:
                        bucket.save(name, source)
                    finally:
                        bucket.file_overwrite = False
                copied += 1
            else:
                skipped += 1
            if options["delete_local"] and not options["dry_run"] and disk.exists(name):
                if bucket.size(name) != os.path.getsize(disk.path(name)):
                    self.stderr.write(f"size differs, keeping the disk copy: {name}")
                    continue
                freed += disk.size(name)
                disk.delete(name)

        self.stdout.write(self.style.SUCCESS(
            f"{copied} copied, {skipped} already in the bucket, {missing} missing; "
            f"{freed / MB:.1f} MB freed from the disk."))
