"""Populate the local database with realistic demo data for manual UI testing.

Why a management command (and not a fixture or a data migration)?
    * Fixtures (``loaddata``) cannot hash passwords, hardcode primary keys, and
      carry static dates that silently go stale -- an "upcoming" event becomes a
      past one. This command hashes passwords properly (demo logins actually
      work) and computes every date relative to *today*, so upcoming events,
      visits, and job deadlines are always in the future.
    * A data migration would run in *every* environment, including Cornell
      Media3 production -- you never want fake users there. This command is
      explicit and opt-in, and it refuses to run when ``DEBUG`` is off unless
      ``--force`` is given.

It is idempotent: every object is created via ``get_or_create`` /
``update_or_create`` keyed on a natural field, so running it repeatedly (or on a
fresh checkout on another machine) converges to the same dataset with no
duplicates.

Usage::

    python manage.py seed_demo                # create or refresh demo data
    python manage.py seed_demo --reset        # delete demo data first, then seed
    python manage.py seed_demo --password foo # override the shared demo password
    python manage.py seed_demo --force        # allow running when DEBUG=False
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser, Profile
from events.models import Event
from jobs.models import Job
from publications.models import Author, Publication
from seminars.models import Seminar, University

# All demo users share this e-mail domain so ``--reset`` can find and remove
# exactly the accounts this command created, and nothing else.
DEMO_DOMAIN = "laborhub.demo"
DEFAULT_PASSWORD = "demo12345"

# Marker stored on demo-created universities so they can be found on --reset.
DEMO_SOURCE = "demo"


def _email(local_part):
    return f"{local_part}@{DEMO_DOMAIN}"


# (local_part, first, last, role, advisor_local_part, profile{...})
RESEARCHERS = [
    (
        "rosa.researcher", "Rosa", "Martinez", CustomUser.Role.RESEARCHER, None,
        {
            "position": "Associate Professor of Economics",
            "education": "PhD Economics, MIT",
            "country_code": "US",
            "website": "https://example.com/rosa",
            "biography": "Rosa studies active labor market policies and wage dynamics.",
            "research_interests": ["Active Labor Market Policies", "Wage Inequality"],
        },
    ),
    (
        "sam.scholar", "Sam", "Okafor", CustomUser.Role.RESEARCHER, None,
        {
            "position": "Assistant Professor",
            "education": "PhD Economics, LSE",
            "country_code": "GB",
            "website": "https://example.com/sam",
            "biography": "Sam works on migration, development, and intergenerational mobility.",
            "research_interests": ["Migration", "Intergenerational Mobility"],
        },
    ),
]

STUDENTS = [
    (
        "sophia.student", "Sophia", "Chen", CustomUser.Role.STUDENT, "rosa.researcher",
        {
            "position": "PhD Candidate",
            "education": "MA Economics, Cornell",
            "country_code": "CA",
            "website": "",
            "biography": "Sophia researches the gig economy and non-standard work.",
            "research_interests": ["Gig Economy", "Non-standard Work"],
        },
    ),
    (
        "diego.doctoral", "Diego", "Alvarez", CustomUser.Role.STUDENT, "rosa.researcher",
        {
            "position": "Doctoral Researcher",
            "education": "BA Economics, UBA",
            "country_code": "BR",
            "website": "",
            "biography": "Diego studies education, human capital, and labor supply.",
            "research_interests": ["Education and Human Capital", "Labor Supply"],
        },
    ),
]

ADMINS = [
    (
        "admin", "Ada", "Admin", CustomUser.Role.ADMIN, None,
        {
            "position": "Platform Administrator",
            "education": "MBA",
            "country_code": "US",
            "website": "",
            "biography": "Ada manages the platform and reviews applications.",
            "research_interests": ["Personnel Economics"],
        },
    ),
]

# External (non-user) co-authors, referenced by name only.
EXTERNAL_AUTHORS = ["J. P. Laurent", "Mei Tanaka"]

# (title, author_keys, country_code, topic, keywords, study_url, is_job_market)
# author_keys are either a demo user local-part or an external author name.
PUBLICATIONS = [
    (
        "Education and Human Capital in the Modern Labor Market",
        ["rosa.researcher", "sophia.student"], "US", "Education and Human Capital",
        ["Education and Human Capital", "Labor Supply"],
        "https://example.com/education-human-capital", False,
    ),
    (
        "Active Labor Market Policies and Unemployment Insurance",
        ["rosa.researcher"], "GB", "Active Labor Market Policies",
        ["Active Labor Market Policies", "Unemployment Insurance", "Job Search"],
        "https://example.com/labor-market-policies", True,
    ),
    (
        "Migration, Family, and Intergenerational Mobility",
        ["sam.scholar", "Mei Tanaka"], "CA", "Migration",
        ["Migration", "Intergenerational Mobility", "Inequality"],
        "https://example.com/migration-mobility", False,
    ),
    (
        "AI, Technological Change, and the Gig Economy",
        ["sophia.student", "J. P. Laurent"], "DE", "AI and Technological Change",
        ["AI and Technological Change", "Gig Economy", "Non-standard Work"],
        "https://example.com/ai-gig-economy", True,
    ),
    (
        "Workers' Health, Well-being, and Job Amenities",
        ["diego.doctoral"], "FR", "Workers' Health and Well-being",
        ["Workers' Health and Well-being", "Job Amenities", "Welfare Policy"],
        "https://example.com/health-job-amenities", False,
    ),
]

# (title, description, category, location, host_key, day_offset, hour)
EVENTS = [
    (
        "Labor Economics Reading Group",
        "A weekly discussion of new working papers in applied labor economics.",
        "workshop", "Ives Hall, Cornell University", "rosa.researcher", 7, 15,
    ),
    (
        "Migration and Development Conference",
        "Two-day conference bringing together researchers on migration and development.",
        "conference", "New York, NY", "sam.scholar", 21, 9,
    ),
    (
        "Summer School on Causal Inference",
        "Intensive seasonal school covering modern causal-inference methods.",
        "schools", "Ithaca, NY", "rosa.researcher", 45, 10,
    ),
    (
        "Live Podcast: The Future of Work",
        "A recorded panel on automation, the gig economy, and job quality.",
        "podcast", "Online", "sophia.student", 60, 18,
    ),
]

# Demo universities (name, country_code, website).
UNIVERSITIES = [
    ("Cornell University", "US", "https://cornell.edu"),
    ("London School of Economics", "GB", "https://lse.ac.uk"),
    ("University of Toronto", "CA", "https://utoronto.ca"),
    ("Sciences Po", "FR", "https://sciencespo.fr"),
]

# (visitor_name, visitor_email, affiliation, university_name, posted_by_key,
#  start_offset, end_offset, countries, description)
SEMINARS = [
    (
        "Rosa Martinez", _email("rosa.visit"), "MIT", "Cornell University",
        "rosa.researcher", 10, 14, ["US"],
        "Visiting for a seminar series on wage dynamics; happy to meet students.",
    ),
    (
        "Sam Okafor", _email("sam.visit"), "LSE", "University of Toronto",
        "sam.scholar", 20, 27, ["CA", "GB"],
        "Sabbatical visit focused on migration research collaborations.",
    ),
    (
        "Mei Tanaka", _email("mei.visit"), "University of Tokyo", "Sciences Po",
        "rosa.researcher", 35, None, ["FR", "JP"],
        "",  # Details intentionally left blank to exercise the optional case.
    ),
]

# (title, description, uploader_key, countries, categories, url, deadline_offset)
JOBS = [
    (
        "Assistant Professor of Labor Economics",
        "Tenure-track position in applied labor economics. PhD required.",
        "admin", ["US"], ["assistant_professor"], "https://example.com/jobs/assistant-professor", 45,
    ),
    (
        "Predoctoral Research Fellow",
        "Two-year predoctoral fellowship supporting labor and public economics research.",
        "rosa.researcher", ["US", "GB"], ["predoc"], "https://example.com/jobs/predoc", 30,
    ),
    (
        "Postdoctoral Associate in Migration Studies",
        "Postdoctoral appointment on a funded migration and development project.",
        "sam.scholar", ["CA"], ["postdoc"], "https://example.com/jobs/postdoc", 60,
    ),
    (
        "Open-Rank Professorship in Economics",
        "Senior faculty search open to associate and full professors in labor and public economics.",
        "sam.scholar", ["GB"], ["associate_professor", "full_professor"], "https://example.com/jobs/open-rank", 20,
    ),
    (
        "Research Data Analyst",
        "Support empirical labor research: data cleaning, analysis, and reproducibility.",
        "admin", ["US", "IN"], ["predoc", "postdoc", "other"], "https://example.com/jobs/data-analyst", 90,
    ),
]


class Command(BaseCommand):
    help = "Populate the database with demo data for local UI testing (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all demo data created by this command before seeding.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow running even when DEBUG is False (use with care).",
        )
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Shared password for all demo users (default: {DEFAULT_PASSWORD!r}).",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "Refusing to seed demo data with DEBUG=False. This command is for "
                "local development only. Pass --force if you really mean to run it "
                "against this environment."
            )

        password = options["password"]

        with transaction.atomic():
            if options["reset"]:
                self._reset()

            users = self._seed_users(password)
            self._seed_publications(users)
            self._seed_events(users)
            universities = self._seed_universities()
            self._seed_seminars(users, universities)
            self._seed_jobs(users)

        self.stdout.write(self.style.SUCCESS("\nDemo data ready."))
        self.stdout.write(
            "Log in with any demo account (password: "
            f"{password!r}), e.g. {_email('admin')} (admin) or "
            f"{_email('rosa.researcher')} (researcher)."
        )

    # -- seeding ---------------------------------------------------------------

    def _seed_users(self, password):
        """Create demo users + profiles. Returns {local_part: CustomUser}."""
        users = {}
        created = 0

        # Researchers and admins first so students can reference an advisor.
        for local_part, first, last, role, _advisor, profile_fields in (
            RESEARCHERS + ADMINS + STUDENTS
        ):
            email = _email(local_part)
            is_admin = role == CustomUser.Role.ADMIN
            user, was_created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": role,
                    "is_active": True,
                    "is_staff": is_admin,
                    "is_superuser": is_admin,
                },
            )
            if was_created:
                user.set_password(password)
                user.save()
                created += 1
            users[local_part] = user

        # Second pass: wire student -> advisor now that all users exist.
        for local_part, _first, _last, role, advisor_key, _profile in STUDENTS:
            if advisor_key and advisor_key in users:
                user = users[local_part]
                user.advisor = users[advisor_key]
                user.save()

        # Update the auto-created profiles (a post_save signal creates a blank
        # Profile for every new user, so we update rather than create).
        for local_part, _first, _last, _role, _advisor, profile_fields in (
            RESEARCHERS + ADMINS + STUDENTS
        ):
            Profile.objects.filter(user=users[local_part]).update(**profile_fields)

        self.stdout.write(f"Users: {created} created, {len(users) - created} existing.")
        return users

    def _author_for(self, key, users):
        """Resolve an author key to an Author (user-linked or external by name)."""
        if key in users:
            author, _ = Author.objects.get_or_create(user=users[key], name="")
        else:
            author, _ = Author.objects.get_or_create(user=None, name=key)
        return author

    def _seed_publications(self, users):
        created = 0
        for title, author_keys, country, topic, keywords, url, is_job_market in PUBLICATIONS:
            pub, was_created = Publication.objects.update_or_create(
                title=title,
                defaults={
                    "abstract": f"{topic}: a demo abstract for local UI testing.",
                    "country_code": country,
                    "topic": topic,
                    "keywords": keywords,
                    "study_url": url,
                    "is_job_market": is_job_market,
                    "status": "approved",
                },
            )
            pub.authors.set([self._author_for(k, users) for k in author_keys])
            created += int(was_created)
        self.stdout.write(f"Publications: {created} created, {len(PUBLICATIONS) - created} updated.")

    def _seed_events(self, users):
        now = timezone.now()
        created = 0
        for title, description, category, location, host_key, day_offset, hour in EVENTS:
            event_dt = (now + timedelta(days=day_offset)).replace(
                hour=hour, minute=0, second=0, microsecond=0
            )
            _event, was_created = Event.objects.update_or_create(
                title=title,
                defaults={
                    "description": description,
                    "category": category,
                    "location": location,
                    "host": users.get(host_key),
                    "date": event_dt,
                    "status": "approved",
                },
            )
            created += int(was_created)
        self.stdout.write(f"Events: {created} created, {len(EVENTS) - created} updated.")

    def _seed_universities(self):
        """Create demo universities. Returns {name: University}."""
        universities = {}
        created = 0
        for name, country, website in UNIVERSITIES:
            external_id = name.lower().replace(" ", "-")
            uni, was_created = University.objects.get_or_create(
                source=DEMO_SOURCE,
                external_id=external_id,
                defaults={"name": name, "country_code": country, "website": website},
            )
            universities[name] = uni
            created += int(was_created)
        self.stdout.write(f"Universities: {created} created, {len(UNIVERSITIES) - created} existing.")
        return universities

    def _seed_seminars(self, users, universities):
        today = timezone.localdate()
        created = 0
        for (name, email, affiliation, uni_name, posted_by_key,
             start_offset, end_offset, countries, description) in SEMINARS:
            _seminar, was_created = Seminar.objects.update_or_create(
                visitor_email=email,
                defaults={
                    "visitor_name": name,
                    "visitor_affiliation": affiliation,
                    "university": universities.get(uni_name),
                    "university_name": uni_name,
                    "posted_by": users.get(posted_by_key),
                    "visit_start": today + timedelta(days=start_offset),
                    "visit_end": (
                        today + timedelta(days=end_offset) if end_offset is not None else None
                    ),
                    "countries": countries,
                    "description": description,
                },
            )
            created += int(was_created)
        self.stdout.write(f"Seminars (visits): {created} created, {len(SEMINARS) - created} updated.")

    def _seed_jobs(self, users):
        today = timezone.localdate()
        created = 0
        for (title, description, uploader_key, countries,
             categories, url, deadline_offset) in JOBS:
            _job, was_created = Job.objects.update_or_create(
                title=title,
                defaults={
                    "description": description,
                    "uploader": users.get(uploader_key),
                    "countries": countries,
                    "categories": categories,
                    "url": url,
                    "deadline": today + timedelta(days=deadline_offset),
                },
            )
            created += int(was_created)
        self.stdout.write(f"Jobs: {created} created, {len(JOBS) - created} updated.")

    # -- reset -----------------------------------------------------------------

    def _reset(self):
        """Delete only the data this command creates (matched by natural keys)."""
        Job.objects.filter(title__in=[j[0] for j in JOBS]).delete()
        Seminar.objects.filter(visitor_email__endswith=f"@{DEMO_DOMAIN}").delete()
        Event.objects.filter(title__in=[e[0] for e in EVENTS]).delete()
        Publication.objects.filter(title__in=[p[0] for p in PUBLICATIONS]).delete()
        Author.objects.filter(name__in=EXTERNAL_AUTHORS).delete()
        University.objects.filter(source=DEMO_SOURCE).delete()
        # Deleting the users cascades their Profiles and user-linked Authors.
        CustomUser.objects.filter(email__endswith=f"@{DEMO_DOMAIN}").delete()
        self.stdout.write(self.style.WARNING("Reset: existing demo data deleted."))
