from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from seminars.hipolabs import fetch_universities
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
        parser.add_argument(
            '--if-empty',
            action='store_true',
            help=(
                'Skip the import when the University table already has rows. '
                'Deprecated: every deploy now re-syncs regardless, so a table '
                'that was only partially populated by an interrupted earlier '
                'run repairs itself on the next deploy instead of staying '
                'stuck. Kept only for anyone still passing it by hand.'
            ),
        )

    def handle(self, *args, **options):
        country = (options.get('country') or '').strip()
        source = (options.get('source') or 'hipolabs').strip()
        limit = int(options.get('limit') or 0)

        if options.get('if_empty') and University.objects.exists():
            self.stdout.write('University table already populated; skipping import.')
            return

        try:
            rows = fetch_universities(country)
        except Exception as exc:
            raise CommandError(f'Failed to fetch universities: {exc}') from exc

        if limit:
            rows = rows[:limit]

        # Load what's on file for this source in one query, keyed the same
        # way update_or_create used to look rows up, so the whole import can
        # become one bulk_create + one bulk_update inside a single
        # transaction: either every row lands, or (on any failure partway
        # through, e.g. the deploy container being recycled) none do, rather
        # than leaving the table's earlier partial state to strand a country
        # part-way through the alphabet forever.
        existing_by_key = {
            (uni.source, uni.external_id): uni
            for uni in University.objects.filter(source=source)
        }

        to_create = []
        to_update = []
        seen_keys = set()
        processed = 0

        for row in rows:
            name = (row.get('name') or '').strip()
            if not name:
                continue

            country_name = (row.get('country') or '').strip()
            alpha_two = (row.get('alpha_two_code') or '').strip().upper()

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

            key = (source, external_id)
            if key in seen_keys:
                # The upstream feed occasionally repeats a row; keep the
                # first (bulk_update can't target the same row twice).
                continue
            seen_keys.add(key)
            processed += 1

            existing = existing_by_key.get(key)
            if existing is None:
                to_create.append(University(
                    source=source, external_id=external_id,
                    name=name, country_code=alpha_two, website=website,
                ))
            else:
                existing.name = name
                existing.country_code = alpha_two
                existing.website = website
                to_update.append(existing)

        with transaction.atomic():
            if to_create:
                University.objects.bulk_create(to_create)
            if to_update:
                University.objects.bulk_update(
                    to_update, ['name', 'country_code', 'website'])

        self.stdout.write(
            self.style.SUCCESS(
                f'University import finished: processed={processed}, '
                f'created={len(to_create)}, updated={len(to_update)}.'
            )
        )
