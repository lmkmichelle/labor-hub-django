"""The seed_examples command, which is safe to run against the live site.

The properties that matter are that it creates no accounts, never touches real
submissions, and can be undone exactly -- those are what make it safe in
production, unlike seed_demo.
"""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from events.models import Event
from jobs.models import Job
from publications.models import Author, Publication
from seminars.models import Seminar

CONTENT_MODELS = (Publication, Event, Job, Seminar)


def run(*args):
    out = StringIO()
    call_command("seed_examples", *args, stdout=out, stderr=out)
    return out.getvalue()


class SeedExamplesTests(TestCase):
    def test_creates_exactly_one_of_each_type(self):
        run()
        for model in CONTENT_MODELS:
            with self.subTest(model=model.__name__):
                self.assertEqual(model.objects.count(), 1)

    def test_every_item_is_flagged_and_approved(self):
        """Both are required: the flag drives the badge, approval drives visibility."""
        run()
        for model in CONTENT_MODELS:
            with self.subTest(model=model.__name__):
                item = model.objects.get()
                self.assertTrue(item.is_example)
                self.assertEqual(item.status, "approved")

    def test_creates_no_user_accounts(self):
        """The whole point of not reusing seed_demo -- it must never make users."""
        run()
        self.assertEqual(CustomUser.objects.count(), 0)

    def test_ownership_is_unset_by_default(self):
        """So example content never appears on a real member's profile."""
        run()
        self.assertIsNone(Job.objects.get().uploader)
        self.assertIsNone(Event.objects.get().host)
        self.assertIsNone(Seminar.objects.get().posted_by)

    def test_dates_are_in_the_future(self):
        run()
        today = timezone.localdate()
        self.assertGreater(Job.objects.get().deadline, today)
        self.assertGreater(Event.objects.get().date, timezone.now())
        self.assertGreater(Seminar.objects.get().visit_start, today)

    def test_visit_stays_in_the_upcoming_window(self):
        """Mirrors the filter SeminarsListView uses for the Upcoming tab."""
        run()
        visit = Seminar.objects.get()
        self.assertGreaterEqual(visit.visit_end, timezone.localdate())

    def test_publication_has_an_unlinked_author(self):
        """An external Author, so the fake paper is not attached to a member."""
        run()
        author = Publication.objects.get().authors.get()
        self.assertIsNone(author.user)

    def test_running_twice_does_not_duplicate(self):
        run()
        run()
        for model in CONTENT_MODELS:
            with self.subTest(model=model.__name__):
                self.assertEqual(model.objects.count(), 1)

    def test_owner_option_attributes_the_content(self):
        member = CustomUser.objects.create_user(
            email="owner@example.com", password="pass12345",
            first_name="A", last_name="B", is_active=True,
        )
        run("--owner", "owner@example.com")
        self.assertEqual(Job.objects.get().uploader, member)
        self.assertEqual(Seminar.objects.get().posted_by, member)

    def test_unknown_owner_is_rejected_before_anything_is_created(self):
        with self.assertRaises(CommandError):
            run("--owner", "nobody@example.com")
        for model in CONTENT_MODELS:
            with self.subTest(model=model.__name__):
                self.assertEqual(model.objects.count(), 0)


class SeedExamplesRemoveTests(TestCase):
    def test_remove_clears_every_example(self):
        run()
        run("--remove")
        for model in CONTENT_MODELS:
            with self.subTest(model=model.__name__):
                self.assertEqual(model.objects.count(), 0)

    def test_remove_leaves_real_submissions_untouched(self):
        real = Job.objects.create(
            title="Example: Postdoctoral Researcher in Labor Economics",
            description="A genuine posting that happens to share the example title.",
            url="https://real.example.edu/jobs/1",
            deadline=timezone.localdate() + timedelta(days=30),
            status="approved",
        )
        run()
        run("--remove")
        self.assertTrue(Job.objects.filter(pk=real.pk).exists())
        self.assertEqual(Job.objects.count(), 1)

    def test_remove_drops_the_placeholder_author(self):
        run()
        run("--remove")
        self.assertFalse(Author.objects.filter(user=None).exists())

    def test_remove_is_safe_when_nothing_was_seeded(self):
        run("--remove")
        for model in CONTENT_MODELS:
            with self.subTest(model=model.__name__):
                self.assertEqual(model.objects.count(), 0)


class ExampleBadgeTests(TestCase):
    """The badge is the whole point of the flag being public."""

    def setUp(self):
        run()

    def test_badge_shows_on_list_pages(self):
        for url in ["/jobs/", "/events/", "/visits/", "/publications/"]:
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), "Example")

    def test_badge_shows_on_detail_pages(self):
        for model, url in [
            (Job, "/jobs/{}/"),
            (Event, "/events/{}/"),
            (Seminar, "/visits/{}/"),
            (Publication, "/publications/{}/"),
        ]:
            with self.subTest(model=model.__name__):
                response = self.client.get(url.format(model.objects.get().pk))
                self.assertContains(response, "Example")

    def test_real_content_gets_no_badge(self):
        run("--remove")
        Job.objects.create(
            title="A Real Job", description="Real.",
            url="https://real.example.edu/jobs/1",
            deadline=timezone.localdate() + timedelta(days=30),
            status="approved",
        )
        response = self.client.get("/jobs/")
        self.assertContains(response, "A Real Job")
        self.assertNotContains(response, "_example_badge")
        self.assertNotContains(response, "bg-amber-100")


class ExamplePaperPillTests(TestCase):
    """The example paper isn't actually part of the discussion series."""

    def setUp(self):
        run()
        self.paper = Publication.objects.get()

    def test_no_discussion_series_pill_on_the_publications_list(self):
        response = self.client.get("/publications/")
        self.assertNotContains(response, "Discussion Series #")

    def test_no_discussion_series_pill_on_the_home_page(self):
        response = self.client.get("/")
        self.assertNotContains(response, "Discussion Series #")

    def test_real_paper_still_gets_the_pill(self):
        run("--remove")
        author = Author.objects.create(user=None, name="Real Author")
        paper = Publication.objects.create(
            title="A Real Paper", abstract="Real.",
            study_url="https://real.example.edu", status="approved",
        )
        paper.authors.set([author])
        response = self.client.get("/publications/")
        self.assertContains(response, f"Discussion Series #{paper.id}")

    def test_no_discussion_series_text_on_the_example_event_card(self):
        """Pre-existing copy-paste bug: the home page event card also printed
        this text, which never made sense for an event regardless of is_example."""
        response = self.client.get("/")
        self.assertNotContains(response, "Discussion Series #")
