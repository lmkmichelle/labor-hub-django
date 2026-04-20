import json
from urllib.parse import urlencode
from urllib.request import urlopen

from django.core.management.base import BaseCommand, CommandError

from seminars.models import University


class Command(BaseCommand):
    help = 'Import universities from the Hipolabs public universities API.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--country',
            default='',
            help='Filter by country name, e.g. "United States" or "Kenya".',
        )
        parser.add_argument(
            '--source',
            default='hipolabs',
            help='Source label saved on imported rows.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Maximum number of rows to import (0 = no limit).',
        )

    def handle(self, *args, **options):
        country = (options.get('country') or '').strip()
        source = (options.get('source') or 'hipolabs').strip()
        limit = int(options.get('limit') or 0)

        query = {}
        if country:
            query['country'] = country

        url = 'http://universities.hipolabs.com/search'
        if query:
            url = f"{url}?{urlencode(query)}"

        try:
            with urlopen(url, timeout=30) as response:
                payload = response.read().decode('utf-8')
        except Exception as exc:
            raise CommandError(f'Failed to fetch universities: {exc}') from exc

        try:
            rows = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise CommandError(f'Failed to parse universities payload: {exc}') from exc

        if not isinstance(rows, list):
            raise CommandError('Unexpected universities API response format.')

        created = 0
        updated = 0
        processed = 0

        for row in rows:
            if limit and processed >= limit:
                break
            if not isinstance(row, dict):
                continue

            name = (row.get('name') or '').strip()
            country_name = (row.get('country') or '').strip()
            alpha_two = (row.get('alpha_two_code') or '').strip().upper()

            if not name:
                continue

            websites = row.get('web_pages') or []
            website = ''
            if isinstance(websites, list) and websites:
                website = str(websites[0]).strip()

            domains = row.get('domains') or []
            external_id = ''
            if isinstance(domains, list) and domains:
                external_id = str(domains[0]).strip().lower()
            if not external_id:
                external_id = f"{name.lower()}::{country_name.lower()}"

            defaults = {
                'name': name,
                'country_code': alpha_two,
                'website': website,
            }

            university, was_created = University.objects.update_or_create(
                source=source,
                external_id=external_id,
                defaults=defaults,
            )

            if was_created:
                created += 1
            else:
                updated += 1

            processed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'University import finished: processed={processed}, created={created}, updated={updated}.'
            )
        )

