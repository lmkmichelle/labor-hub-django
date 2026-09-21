import io
import zipfile
from urllib.request import urlopen

from django.core.management.base import BaseCommand, CommandError

from core.constants import COUNTRY_CHOICES
from core.models import City

CITIES_URL = 'https://download.geonames.org/export/dump/cities15000.zip'
ADMIN1_URL = 'https://download.geonames.org/export/dump/admin1CodesASCII.txt'

# GeoNames publishes a country code that isn't one of ours (Kosovo, "XK") --
# skip rows we can't map onto core.constants.COUNTRY_CHOICES rather than
# raising, since a handful of unmappable rows shouldn't abort the whole import.


class Command(BaseCommand):
    help = 'Import cities (population >= 15,000) from the GeoNames public dataset.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--country',
            default='',
            help='Filter by ISO-3166 alpha-2 country code, e.g. "US".',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Maximum number of rows to import (0 = no limit).',
        )
        parser.add_argument(
            '--if-empty',
            action='store_true',
            help=(
                'Skip the import when the City table already has rows. '
                'Lets the Upsun deploy hook run this once without re-fetching '
                'the full dataset on every deploy.'
            ),
        )

    def handle(self, *args, **options):
        country_filter = (options.get('country') or '').strip().upper()
        limit = int(options.get('limit') or 0)

        if options.get('if_empty') and City.objects.exists():
            self.stdout.write('City table already populated; skipping import.')
            return

        admin1_names = self._fetch_admin1_names()
        rows = self._fetch_city_rows()

        valid_codes = {code for code, _ in COUNTRY_CHOICES}

        cities = []
        processed = 0
        skipped = 0

        for row in rows:
            if limit and processed >= limit:
                break

            fields = row.split('\t')
            if len(fields) < 15:
                continue

            geoname_id = fields[0].strip()
            name = fields[1].strip()
            country_code = fields[8].strip().upper()
            admin1_code = fields[10].strip()
            population_raw = fields[14].strip()

            if not geoname_id or not name:
                continue
            if country_filter and country_code != country_filter:
                continue
            if country_code not in valid_codes:
                skipped += 1
                continue

            try:
                population = int(population_raw)
            except ValueError:
                population = 0

            admin1_name = admin1_names.get(f"{country_code}.{admin1_code}", '')

            cities.append(City(
                geoname_id=int(geoname_id),
                name=name,
                country_code=country_code,
                admin1_name=admin1_name,
                population=population,
            ))
            processed += 1

        City.objects.bulk_create(cities, ignore_conflicts=True, batch_size=1000)

        self.stdout.write(
            self.style.SUCCESS(
                f'City import finished: processed={processed}, skipped={skipped} '
                f'(unrecognized country code).'
            )
        )

    def _fetch_city_rows(self):
        try:
            with urlopen(CITIES_URL, timeout=60) as response:
                payload = response.read()
        except Exception as exc:
            raise CommandError(f'Failed to fetch GeoNames cities archive: {exc}') from exc

        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                with archive.open('cities15000.txt') as fh:
                    text = fh.read().decode('utf-8')
        except (zipfile.BadZipFile, KeyError) as exc:
            raise CommandError(f'Unexpected GeoNames archive contents: {exc}') from exc

        return text.splitlines()

    def _fetch_admin1_names(self):
        """Map "CC.admin1code" -> readable region name, e.g. "US.NY" -> "New York".

        Best-effort: an empty/failed fetch just means cities render without a
        state/region qualifier, not an import failure.
        """
        try:
            with urlopen(ADMIN1_URL, timeout=30) as response:
                text = response.read().decode('utf-8')
        except Exception:
            return {}

        names = {}
        for line in text.splitlines():
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            code, name = parts[0].strip(), parts[1].strip()
            if code:
                names[code] = name
        return names
