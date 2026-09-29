from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from seminars import hipolabs
from seminars.models import University


class ImportUniversitiesCommandTests(TestCase):
    def test_if_empty_skips_when_table_populated(self):
        University.objects.create(
            name="Cornell", country_code="US", source="manual", external_id="cornell",
        )
        with patch.object(hipolabs, "urlopen") as mock_urlopen:
            out = StringIO()
            call_command("import_universities", "--if-empty", stdout=out)

        mock_urlopen.assert_not_called()
        self.assertIn("already populated", out.getvalue())

    def test_creates_new_rows(self):
        cm = _fake_urlopen(
            '[{"name": "Test U", "country": "United States", '
            '"alpha_two_code": "US", "web_pages": ["https://test.edu"], '
            '"domains": ["test.edu"]}]'
        )
        with patch.object(hipolabs, "urlopen", return_value=cm):
            call_command("import_universities", stdout=StringIO())

        self.assertTrue(University.objects.filter(name="Test U").exists())

    def test_fetches_over_http(self):
        """hipolabs' API only listens on plain HTTP -- port 443 refuses the
        connection outright (confirmed against the real service, not an
        artifact of a test mock). Requesting https:// here fails every time,
        which is exactly the bug that left production's University table
        stuck at whatever it had been seeded with."""
        cm = _fake_urlopen("[]")
        with patch.object(hipolabs, "urlopen", return_value=cm) as mock_urlopen:
            call_command("import_universities", stdout=StringIO())

        called_url = mock_urlopen.call_args[0][0]
        self.assertTrue(called_url.startswith("http://"))

    def test_running_twice_does_not_duplicate_rows(self):
        """Regression for the production symptom: re-running the import
        (now on every deploy, not just --if-empty) must update the existing
        row in place rather than creating a second one for the same
        university, and must not silently drop rows already on file for a
        different, unrelated part of the alphabet."""
        payload = (
            '[{"name": "Test U", "country": "United States", '
            '"alpha_two_code": "US", "web_pages": ["https://test.edu"], '
            '"domains": ["test.edu"]}]'
        )
        cm = _fake_urlopen(payload)
        with patch.object(hipolabs, "urlopen", return_value=cm):
            call_command("import_universities", stdout=StringIO())
        cm = _fake_urlopen(payload)
        with patch.object(hipolabs, "urlopen", return_value=cm):
            call_command("import_universities", stdout=StringIO())

        self.assertEqual(University.objects.filter(name="Test U").count(), 1)

    def test_a_second_run_updates_a_changed_field(self):
        cm = _fake_urlopen(
            '[{"name": "Test U", "country": "United States", '
            '"alpha_two_code": "US", "web_pages": ["https://old.edu"], '
            '"domains": ["test.edu"]}]'
        )
        with patch.object(hipolabs, "urlopen", return_value=cm):
            call_command("import_universities", stdout=StringIO())

        cm = _fake_urlopen(
            '[{"name": "Test U", "country": "United States", '
            '"alpha_two_code": "US", "web_pages": ["https://new.edu"], '
            '"domains": ["test.edu"]}]'
        )
        with patch.object(hipolabs, "urlopen", return_value=cm):
            call_command("import_universities", stdout=StringIO())

        university = University.objects.get(name="Test U")
        self.assertEqual(university.website, "https://new.edu")

    def test_a_fetch_failure_raises_a_command_error_and_writes_nothing(self):
        """The old ``|| true`` shielded a failed fetch entirely -- a partial
        import could still commit whatever rows it had processed before the
        exception. Nothing should be written on a failed fetch at all."""
        with patch.object(hipolabs, "urlopen", side_effect=OSError("boom")):
            with self.assertRaises(CommandError):
                call_command("import_universities", stdout=StringIO())

        self.assertEqual(University.objects.count(), 0)


class _fake_urlopen:
    """Minimal context-manager stand-in for urllib.request.urlopen."""

    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body.encode("utf-8")
