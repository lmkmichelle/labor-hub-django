"""List (and optionally delete) uploaded files that no database row refers to.

Django never deletes a file when the field pointing at it is replaced or its row is
removed, so abandoned copies pile up on the app's small persistent disk -- before
this command existed, mostly the plain "pending" copy of each paper that the
covered PDF replaced, and a fresh covered PDF for every edit.

    python manage.py reclaim_media            # dry run: lists, deletes nothing
    python manage.py reclaim_media --apply    # deletes what the dry run listed

A file is *reclaimable* only when no FileField/ImageField on any model references it
AND it is older than ``--min-age-hours`` (default 24), so an upload that is being
saved right now is never touched. Only files under MEDIA_ROOT on the local
filesystem are considered; anything referenced by the database is always kept.
"""
import os
import time
from collections import defaultdict

from django.apps import apps
from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import models

MB = 1024 * 1024


def referenced_names():
    """Every stored file name (relative to MEDIA_ROOT, '/' separated) a model uses."""
    names = set()
    for model in apps.get_models():
        if model._meta.abstract or model._meta.proxy:
            continue
        for field in model._meta.concrete_fields:
            if not isinstance(field, models.FileField):
                continue
            values = (model._base_manager.exclude(**{field.name: ''})
                      .exclude(**{f'{field.name}__isnull': True})
                      .values_list(field.name, flat=True))
            names.update(str(value).replace(os.sep, '/') for value in values)
    return names


def scan_media(root):
    """Yield (relative_name, size_bytes, mtime) for every file under ``root``."""
    for folder, _dirs, files in os.walk(root):
        for filename in files:
            path = os.path.join(folder, filename)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            yield os.path.relpath(path, root).replace(os.sep, '/'), stat.st_size, stat.st_mtime


class Command(BaseCommand):
    help = "List (dry run) or delete uploaded files that no database row refers to."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Delete the reclaimable files (default: only list them).")
        parser.add_argument("--min-age-hours", type=float, default=24,
                            help="Never touch files newer than this (default 24).")

    def handle(self, *args, **options):
        if not isinstance(default_storage, FileSystemStorage):
            raise CommandError("Only local filesystem media storage is supported.")
        root = str(settings.MEDIA_ROOT)
        if not os.path.isdir(root):
            raise CommandError(f"MEDIA_ROOT does not exist: {root}")

        used = referenced_names()
        cutoff = time.time() - options["min_age_hours"] * 3600
        kept = [0, 0]
        too_new = [0, 0]
        reclaim = []
        for name, size, mtime in scan_media(root):
            if name in used:
                kept[0] += 1
                kept[1] += size
            elif mtime > cutoff:
                too_new[0] += 1
                too_new[1] += size
            else:
                reclaim.append((name, size, mtime))

        by_folder = defaultdict(list)
        for entry in reclaim:
            by_folder[os.path.dirname(entry[0]) or "(media root)"].append(entry)

        self.stdout.write(f"Referenced by the database (kept): {kept[0]} files, {kept[1] / MB:.1f} MB")
        if too_new[0]:
            self.stdout.write(
                f"Unreferenced but newer than {options['min_age_hours']:g}h (left alone): "
                f"{too_new[0]} files, {too_new[1] / MB:.1f} MB")
        self.stdout.write("")
        self.stdout.write("Reclaimable (no database row refers to them):")
        for folder in sorted(by_folder):
            entries = sorted(by_folder[folder], key=lambda e: -e[1])
            self.stdout.write(
                f"  {folder}/  {len(entries)} files, {sum(e[1] for e in entries) / MB:.1f} MB")
            for name, size, mtime in entries:
                stamp = time.strftime("%Y-%m-%d", time.gmtime(mtime))
                self.stdout.write(f"    {size / MB:7.1f} MB  {stamp}  {os.path.basename(name)}")
        total = sum(e[1] for e in reclaim)
        self.stdout.write("")
        self.stdout.write(f"Total reclaimable: {len(reclaim)} files, {total / MB:.1f} MB")

        if not options["apply"]:
            self.stdout.write(self.style.WARNING(
                "Dry run: nothing was deleted. Re-run with --apply to delete these files."))
            return
        deleted = 0
        for name, _size, _mtime in reclaim:
            try:
                os.remove(os.path.join(root, name))
                deleted += 1
            except OSError as exc:
                self.stderr.write(f"could not delete {name}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} files ({total / MB:.1f} MB)."))
