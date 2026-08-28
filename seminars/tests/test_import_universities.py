from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from seminars.management.commands import import_universities
from seminars.models import University


class ImportUniversitiesCommandTests(TestCase):
    def test_if_empty_skips_when_table_populated(self):
        University.objects.create(
            name="Cornell", country_code="US", source="manual", external_id="cornell",
        )
        with patch.object(import_universities, "urlopen") as mock_urlopen:
            out = StringIO()
            call_command("import_universities", "--if-empty", stdout=out)

        mock_urlopen.assert_not_called()
        self.assertIn("already populated", out.getvalue())

    def test_if_empty_runs_when_table_empty(self):
        payload = (
            '[{"name": "Test U", "country": "United States", '
            '"alpha_two_code": "US", "web_pages": ["https://test.edu"], '
            '"domains": ["test.edu"]}]'
        )
        cm = _fake_urlopen(payload)
        with patch.object(import_universities, "urlopen", return_value=cm):
            call_command("import_universities", "--if-empty", stdout=StringIO())

        self.assertTrue(University.objects.filter(name="Test U").exists())

    def test_fetches_over_https(self):
        cm = _fake_urlopen("[]")
        with patch.object(import_universities, "urlopen", return_value=cm) as mock_urlopen:
            call_command("import_universities", stdout=StringIO())

        called_url = mock_urlopen.call_args[0][0]
        self.assertTrue(called_url.startswith("https://"))


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
