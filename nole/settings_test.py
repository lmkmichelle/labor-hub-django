"""Test settings: deterministic, fast, and independent of a local ``.env``.

This module imports the project settings and then overrides everything that would
otherwise make the test suite slow, non-deterministic, or dependent on prebuilt
assets / TLS. Use it for CI and locally:

    python manage.py test --settings=nole.settings_test

Key overrides and *why* they are needed:

* ``SECRET_KEY`` is fixed so tests never depend on a real secret being exported
  (the base settings read ``DJANGO_SECRET_KEY`` from the environment).
* ``COMPRESS_ENABLED``/``COMPRESS_OFFLINE`` are forced off. ``base.html`` wraps its
  CSS in ``{% compress css %}``; with offline compression on, rendering any page
  that extends the base template fails unless ``manage.py compress`` was run first.
* ``SECURE_SSL_REDIRECT`` is forced off; otherwise every test-client request over
  HTTP would return a 301 to HTTPS.
* An in-memory SQLite database is used for speed, *unless* a concrete engine (e.g.
  MySQL for the production-parity CI job) is requested via ``DATABASE_ENGINE`` — in
  that case the base settings' database configuration is kept as-is.
"""

import os
import tempfile

from .settings import *  # noqa: F401,F403

# A fixed, obviously-non-production key so tests never depend on a real secret.
SECRET_KEY = "test-secret-key-not-for-production"  # noqa: S105

DEBUG = False

# base.html uses {% compress css %}; keep the tag inert so template rendering does
# not require a prebuilt offline manifest.
COMPRESS_ENABLED = False
COMPRESS_OFFLINE = False

# Do not force HTTPS (would 301 every test-client request) and drop transport-only
# cookie flags so the HTTP test client behaves normally.
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# The test client and rendered absolute URLs can use any host.
ALLOWED_HOSTS = ["*"]

# Fast hashing keeps the user-creation-heavy account tests quick.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Keep e-mails in memory so tests can assert on mail.outbox (password reset, etc.).
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Never touch S3 during tests, regardless of USE_S3 in the environment.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Write uploaded files (e.g. cropped avatars) to a throwaway temp directory so the
# working tree stays clean.
MEDIA_ROOT = tempfile.mkdtemp(prefix="laborhub-test-media-")

# Use a fast in-memory SQLite database unless a concrete engine was explicitly
# requested (the MySQL production-parity CI job sets DATABASE_ENGINE=mysql and
# relies on the base settings' connection configuration). An empty/unset value is
# treated as SQLite.
if (os.environ.get("DATABASE_ENGINE") or "sqlite3") == "sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
