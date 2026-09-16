import io
import zipfile
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from core.models import City


def make_cities_zip(rows):
    """Build an in-memory zip matching GeoNames' cities15000.zip layout."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('cities15000.txt', '\n'.join(rows))
    return buffer.getvalue()


def geoname_row(geoname_id, name, country_code, admin1_code, population):
    # Matches the 19-column GeoNames main table layout; only the columns the
    # importer reads (0, 1, 8, 10, 14) carry real values.
    fields = [''] * 19
    fields[0] = str(geoname_id)
    fields[1] = name
    fields[8] = country_code
    fields[10] = admin1_code
    fields[14] = str(population)
    return '\t'.join(fields)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ImportCitiesCommandTests(TestCase):
    def _urlopen_side_effect(self, cities_payload, admin1_payload):
        def side_effect(url, timeout=None):
            if 'cities15000' in url:
                return FakeResponse(cities_payload)
            return FakeResponse(admin1_payload)
        return side_effect

    def test_imports_cities_and_resolves_admin1_name(self):
        cities_payload = make_cities_zip([
            geoname_row(1, 'Ithaca', 'US', 'NY', 30000),
            geoname_row(2, 'Paris', 'FR', '11', 2000000),
        ])
        admin1_payload = 'US.NY\tNew York\tNew York\t5128638\n'.encode('utf-8')

        with patch(
            'core.management.commands.import_cities.urlopen',
            side_effect=self._urlopen_side_effect(cities_payload, admin1_payload),
        ):
            out = StringIO()
            call_command('import_cities', stdout=out)

        self.assertEqual(City.objects.count(), 2)
        ithaca = City.objects.get(geoname_id=1)
        self.assertEqual(ithaca.admin1_name, 'New York')
        self.assertEqual(ithaca.display_name, 'Ithaca, New York')
        paris = City.objects.get(geoname_id=2)
        self.assertEqual(paris.admin1_name, '')
        self.assertEqual(paris.display_name, 'Paris')

    def test_country_filter(self):
        cities_payload = make_cities_zip([
            geoname_row(1, 'Ithaca', 'US', 'NY', 30000),
            geoname_row(2, 'Paris', 'FR', '11', 2000000),
        ])
        with patch(
            'core.management.commands.import_cities.urlopen',
            side_effect=self._urlopen_side_effect(cities_payload, b''),
        ):
            call_command('import_cities', '--country', 'US', stdout=StringIO())

        self.assertEqual(City.objects.count(), 1)
        self.assertEqual(City.objects.get().country_code, 'US')

    def test_unrecognized_country_code_is_skipped_not_fatal(self):
        cities_payload = make_cities_zip([
            geoname_row(1, 'Pristina', 'XK', '', 200000),
            geoname_row(2, 'Ithaca', 'US', 'NY', 30000),
        ])
        with patch(
            'core.management.commands.import_cities.urlopen',
            side_effect=self._urlopen_side_effect(cities_payload, b''),
        ):
            out = StringIO()
            call_command('import_cities', stdout=out)

        self.assertEqual(City.objects.count(), 1)
        self.assertIn('skipped=1', out.getvalue())

    def test_if_empty_skips_when_already_populated(self):
        City.objects.create(geoname_id=99, name="Existing", country_code="US")
        with patch(
            'core.management.commands.import_cities.urlopen',
        ) as mock_urlopen:
            call_command('import_cities', '--if-empty', stdout=StringIO())
        mock_urlopen.assert_not_called()
        self.assertEqual(City.objects.count(), 1)
