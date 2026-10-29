"""Storage for research-paper PDFs: Upsun object storage (S3), served through Django.

Upsun's bucket is reachable only from inside the project's network, so a browser can
never fetch a file from it. Everything therefore goes through a view: the public
download is `publications.views.publication_download`, and the admin's file links use
`publication_file` (staff only). `url()` points at the latter.

Papers saved before the bucket existed are still on the app's disk. Until
`move_papers_to_bucket` has copied them, reads fall back to that disk copy, so the
deploy that switches storage over does not break a single download.
"""
from django.conf import settings
from django.core.files.storage import FileSystemStorage, storages
from django.urls import reverse
from storages.backends.s3 import S3Storage


def paper_storage():
    """The `papers` entry of settings.STORAGES (a callable so migrations stay stable)."""
    return storages["papers"]


class PaperBucketStorage(S3Storage):
    def _legacy(self):
        """The disk the papers lived on before the bucket, or None if there is none."""
        root = getattr(settings, "MEDIA_ROOT", "")
        return FileSystemStorage(location=root) if root else None

    def _only_on_disk(self, name):
        legacy = self._legacy()
        return legacy if legacy and not super().exists(name) and legacy.exists(name) else None

    def _open(self, name, mode="rb"):
        legacy = self._only_on_disk(name) if "r" in mode else None
        return legacy._open(name, mode) if legacy else super()._open(name, mode)

    def size(self, name):
        legacy = self._only_on_disk(name)
        return legacy.size(name) if legacy else super().size(name)

    def delete(self, name):
        legacy = self._legacy()
        if legacy and legacy.exists(name):
            legacy.delete(name)
        super().delete(name)

    def url(self, name, parameters=None, expire=None, http_method=None):
        return reverse("publication_file", args=[name])

