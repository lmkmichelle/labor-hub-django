"""Create one illustrative item of each content type, safe to run in production.

Why this exists separately from ``seed_demo``
    ``seed_demo`` is explicitly local-only: it creates five fake **users**,
    including a superuser with a shared, documented password, and refuses to run
    unless ``DEBUG`` is on. Running it against the live site would be a security
    problem, not just untidy. This command exists for the opposite situation --
    the real site, during testing, needing one worked example in each section so
    testers can see what a filled-in entry looks like.

How it stays safe there
    * It creates **no users** and touches no account. Ownership fields
      (``uploader``/``host``/``posted_by``) are left null unless ``--owner`` is
      given, so example content never appears on a real member's profile.
    * Every row it writes is flagged ``is_example=True``, which shows an
      "Example" badge on the public site and makes ``--remove`` exact. Nothing
      is matched by title, so a real submission that happens to share a title is
      never touched.
    * It is idempotent: re-running updates the same four rows rather than
      creating more.
    * Contact addresses use ``example.edu``, reserved by RFC 2606, so nobody
      receives mail meant for a fictional visitor.

Usage::

    python manage.py seed_examples                    # create or refresh
    python manage.py seed_examples --owner me@x.edu   # attribute to a member
    python manage.py seed_examples --remove           # delete them all
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser
from events.models import Event
from jobs.models import Job
from publications.models import Author, Publication
from seminars.models import Seminar

EXAMPLE_AUTHOR = "A. Example"


class Command(BaseCommand):
    help = "Create one example job, paper, visit and event (or remove them with --remove)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--remove",
            action="store_true",
            help="Delete every example item instead of creating them.",
        )
        parser.add_argument(
            "--owner",
            default="",
            help=(
                "Email of an existing member to attribute the examples to. "
                "Omitted by default so example content never shows up on a real "
                "member's profile."
            ),
        )

    def handle(self, *args, **options):
        if options["remove"]:
            self._remove()
            return

        owner = self._resolve_owner(options["owner"])
        today = timezone.localdate()
        now = timezone.now()

        with transaction.atomic():
            self._seed_publication()
            self._seed_event(now, owner)
            self._seed_job(today, owner)
            self._seed_visit(today, owner)

        self.stdout.write(
            self.style.SUCCESS(
                "\n4 example items are live: one discussion paper, one event, one "
                "job and one visit, each badged 'Example'.\n"
                "Remove them with:  python manage.py seed_examples --remove"
            )
        )

    # -- helpers --------------------------------------------------------------
    def _resolve_owner(self, email):
        if not email:
            return None
        owner = CustomUser.objects.filter(email__iexact=email.strip()).first()
        if owner is None:
            raise CommandError(f"No member found with the email {email!r}.")
        return owner

    def _report(self, label, created):
        verb = "created" if created else "updated"
        self.stdout.write(f"  {label:18} {verb}")

    # -- seeders --------------------------------------------------------------
    def _seed_publication(self):
        publication, created = Publication.objects.update_or_create(
            is_example=True,
            title="Example: Minimum Wages and Employment in Local Labor Markets",
            defaults={
                "abstract": (
                    "This is an example entry showing what a discussion paper "
                    "looks like on Labor Hub. A real abstract would summarise the "
                    "question, the data and identification strategy, and the main "
                    "finding in a paragraph or two."
                ),
                "study_url": "https://example.edu/papers/minimum-wages",
                "topic": "Minimum wages",
                "keywords": ["Minimum wages", "Labor Demand"],
                "country_code": "US",
                "status": "approved",
            },
        )
        author, _ = Author.objects.get_or_create(user=None, name=EXAMPLE_AUTHOR)
        publication.authors.set([author])
        self._report("discussion paper", created)

    def _seed_event(self, now, owner):
        _, created = Event.objects.update_or_create(
            is_example=True,
            title="Example: Workshop on Applied Labor Economics",
            defaults={
                "description": (
                    "This is an example entry showing what an event looks like on "
                    "Labor Hub. A real description would cover the theme, who "
                    "should attend, and how to submit or register."
                ),
                # Comfortably ahead so it stays on the home page between reseeds.
                "date": now + timedelta(days=45),
                "end_date": now + timedelta(days=46),
                "deadline": now + timedelta(days=21),
                "location": "Ithaca, NY",
                "category": "workshop",
                "host": owner,
                "status": "approved",
            },
        )
        self._report("event", created)

    def _seed_job(self, today, owner):
        _, created = Job.objects.update_or_create(
            is_example=True,
            title="Example: Postdoctoral Researcher in Labor Economics",
            defaults={
                "description": (
                    "This is an example entry showing what a job posting looks "
                    "like on Labor Hub. A real posting would describe the role, "
                    "the start date, and what to include in an application."
                ),
                "url": "https://example.edu/jobs/postdoc-labor-economics",
                "countries": ["US"],
                "categories": ["postdoc"],
                "deadline": today + timedelta(days=60),
                "uploader": owner,
                "status": "approved",
            },
        )
        self._report("job", created)

    def _seed_visit(self, today, owner):
        _, created = Seminar.objects.update_or_create(
            is_example=True,
            visitor_email="visitor@example.edu",
            defaults={
                "visitor_name": "A. Example",
                "visitor_affiliation": "Example University",
                "university_name": "Cornell University",
                "description": (
                    "This is an example entry showing what a visit looks like on "
                    "Labor Hub. A real entry would say what the visitor works on "
                    "and whether they are available to meet or present."
                ),
                # Starts in the future so it stays in the Upcoming tab.
                "visit_start": today + timedelta(days=30),
                "visit_end": today + timedelta(days=37),
                "countries": ["US"],
                "posted_by": owner,
                "status": "approved",
            },
        )
        self._report("visit", created)

    # -- removal --------------------------------------------------------------
    def _remove(self):
        with transaction.atomic():
            counts = {}
            for label, model in (
                ("discussion paper", Publication),
                ("event", Event),
                ("job", Job),
                ("visit", Seminar),
            ):
                queryset = model.objects.filter(is_example=True)
                # Count first: delete() reports cascaded rows too (the paper's
                # author through-rows), which would overstate what was removed.
                counts[label] = queryset.count()
                queryset.delete()
            # Only remove the placeholder author once nothing references it.
            author = Author.objects.filter(user=None, name=EXAMPLE_AUTHOR).first()
            if author is not None and not author.publications.exists():
                author.delete()

        for label, count in counts.items():
            self.stdout.write(f"  {label:18} removed {count}")
        self.stdout.write(
            self.style.SUCCESS(
                f"\nRemoved {sum(counts.values())} example item(s). "
                "Real submissions were not touched."
            )
        )
