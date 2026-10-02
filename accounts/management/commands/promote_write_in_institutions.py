"""One-off backfill: turn existing profiles' write-in institutions into
proper University rows, the same way UserApplication.approve() now does for
new applications (see seminars.models.University.from_write_in).

Only profiles that already have a country set and a typed-in
``university_name`` but no ``university`` selected are touched -- anything
else is left exactly as it is.

Safety, same convention as purge_test_data:
    * No ``--apply`` -> dry run: reports what would be created/linked.
    * ``--apply``    -> writes, inside one transaction.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Profile
from seminars.models import University


class Command(BaseCommand):
    help = "Promote existing profiles' write-in institutions to University rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Actually write the changes. Without this, only reports.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]

        candidates = Profile.objects.filter(
            university__isnull=True, country_code__isnull=False,
        ).exclude(university_name="").exclude(country_code="").select_related("user")

        created = 0
        linked = 0

        def process():
            nonlocal created, linked
            for profile in candidates:
                existing = University.objects.filter(
                    country_code=profile.country_code,
                    name__iexact=profile.university_name,
                ).first()
                action = "link to existing" if existing else "create"
                self.stdout.write(
                    f"{action}: {profile.user.email} -> "
                    f"\"{profile.university_name}\" ({profile.country_code})"
                )
                if existing:
                    linked += 1
                else:
                    created += 1
                if apply_changes:
                    university = University.from_write_in(
                        profile.university_name, profile.country_code)
                    profile.university = university
                    profile.university_name = ""
                    profile.save(update_fields=["university", "university_name"])

        if apply_changes:
            with transaction.atomic():
                process()
        else:
            process()

        verb = "Promoted" if apply_changes else "[dry-run] Would promote"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {created + linked} profile(s): {created} new institution(s), "
            f"{linked} linked to an existing one."
        ))
