"""Remove test users and content left over from a demo or manual testing.

This command never guesses. With no id arguments it only *reports*: it lists
every user and every moderated content row (publications, events, jobs, visits)
with the identifiers you need to decide what is junk. You then re-run it with
explicit ids and ``--confirm`` to delete exactly those rows.

Safety
    * No ids  -> report only, deletes nothing.
    * Ids but no ``--confirm`` -> dry run: prints what *would* be deleted.
    * ``--confirm`` -> deletes, inside one transaction.
    * Superusers are refused unless ``--force`` is also given.
    * Rows flagged ``is_example=True`` (the ``seed_examples`` placeholders) are
      only ever touched when named explicitly by id.

Usage::

    python manage.py purge_test_data
    python manage.py purge_test_data --user-ids 4,7 --job-ids 12 --event-ids 3
    python manage.py purge_test_data --user-ids 4,7 --confirm
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import CustomUser
from events.models import Event
from jobs.models import Job
from publications.models import Publication
from seminars.models import Seminar

CONTENT_MODELS = {
    "publication": Publication,
    "event": Event,
    "job": Job,
    "visit": Seminar,
}


def _parse_ids(raw):
    if not raw:
        return []
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            raise CommandError(f"Not an integer id: {part!r}")
    return ids


class Command(BaseCommand):
    help = "List, or with explicit ids delete, demo/test users and content."

    def add_arguments(self, parser):
        parser.add_argument("--user-ids", default="")
        parser.add_argument("--publication-ids", default="")
        parser.add_argument("--event-ids", default="")
        parser.add_argument("--job-ids", default="")
        parser.add_argument("--visit-ids", default="")
        parser.add_argument(
            "--confirm", action="store_true",
            help="Actually delete. Without it, ids only produce a dry run.",
        )
        parser.add_argument(
            "--force", action="store_true",
            help="Allow deleting a superuser account (still requires --confirm).",
        )

    def handle(self, *args, **options):
        user_ids = _parse_ids(options["user_ids"])
        content_ids = {
            "publication": _parse_ids(options["publication_ids"]),
            "event": _parse_ids(options["event_ids"]),
            "job": _parse_ids(options["job_ids"]),
            "visit": _parse_ids(options["visit_ids"]),
        }
        any_ids = user_ids or any(content_ids.values())

        if not any_ids:
            self._report()
            return

        self._delete(user_ids, content_ids,
                     confirm=options["confirm"], force=options["force"])

    # -- reporting -----------------------------------------------------------

    def _report(self):
        self.stdout.write(self.style.MIGRATE_HEADING("Users"))
        for user in CustomUser.objects.order_by("date_joined"):
            posted = (
                Publication.objects.filter(authors__user=user).count()
                + Event.objects.filter(host=user).count()
                + Job.objects.filter(uploader=user).count()
                + Seminar.objects.filter(posted_by=user).count()
            )
            flags = []
            if user.is_superuser:
                flags.append("superuser")
            elif user.is_staff:
                flags.append("staff")
            self.stdout.write(
                f"  [{user.id}] {user.email}  role={user.role}  "
                f"joined={user.date_joined:%Y-%m-%d}  posted={posted}"
                + (f"  ({', '.join(flags)})" if flags else "")
            )

        for label, model in CONTENT_MODELS.items():
            self.stdout.write(self.style.MIGRATE_HEADING(f"{label.title()}s"))
            for row in model.objects.all().order_by("id"):
                created = getattr(row, "created_at", None) or getattr(
                    row, "applied_at", None)
                created_str = f"{created:%Y-%m-%d}" if created else "?"
                owner = (
                    getattr(row, "host", None)
                    or getattr(row, "uploader", None)
                    or getattr(row, "posted_by", None)
                )
                title = getattr(row, "title", None) or getattr(
                    row, "visitor_name", "")
                example = "  EXAMPLE" if getattr(row, "is_example", False) else ""
                self.stdout.write(
                    f"  [{row.id}] {title!r}  status={row.status}  "
                    f"created={created_str}  "
                    f"owner={owner.email if owner else '-'}{example}"
                )

        self.stdout.write("")
        self.stdout.write(
            "Nothing deleted. Re-run with e.g. --user-ids 4,7 --job-ids 12 "
            "and add --confirm to delete."
        )

    # -- deletion ----------------------------------------------------------

    def _delete(self, user_ids, content_ids, *, confirm, force):
        users = list(CustomUser.objects.filter(id__in=user_ids))
        self._warn_missing("user", user_ids, users)

        supers = [u for u in users if u.is_superuser]
        if supers and not force:
            raise CommandError(
                "Refusing to delete superuser(s): "
                + ", ".join(u.email for u in supers)
                + ". Pass --force to override."
            )

        planned = []
        for label, ids in content_ids.items():
            if not ids:
                continue
            model = CONTENT_MODELS[label]
            rows = list(model.objects.filter(id__in=ids))
            self._warn_missing(label, ids, rows)
            planned.append((label, rows))

        verb = "Deleting" if confirm else "Would delete"
        for user in users:
            self.stdout.write(f"{verb} user [{user.id}] {user.email}")
        for label, rows in planned:
            for row in rows:
                self.stdout.write(f"{verb} {label} [{row.id}] {row}")

        if not confirm:
            self.stdout.write(self.style.WARNING(
                "Dry run. Add --confirm to apply."))
            return

        with transaction.atomic():
            for label, rows in planned:
                for row in rows:
                    row.delete()
            for user in users:
                user.delete()

        self.stdout.write(self.style.SUCCESS("Done."))

    def _warn_missing(self, label, requested, found):
        found_ids = {obj.id for obj in found}
        for missing in sorted(set(requested) - found_ids):
            self.stdout.write(self.style.WARNING(
                f"No {label} with id {missing}; skipping."))
