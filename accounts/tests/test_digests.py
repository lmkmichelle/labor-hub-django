from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.digests import (
    collect_new_content,
    make_unsubscribe_token,
    read_unsubscribe_token,
    send_user_digest,
)
from accounts.models import CustomUser, Profile
from events.models import Event
from jobs.models import Job
from publications.models import Publication
from seminars.models import Seminar


def make_user(email="digest@example.com", frequency=Profile.DigestFrequency.WEEKLY):
    user = CustomUser.objects.create_user(
        email=email, password="pass12345", first_name="Dig", last_name="Est",
        is_active=True,
    )
    user.profile.digest_frequency = frequency
    user.profile.save()
    return user


def make_publication(title, applied_at, status="approved", country_code="US"):
    pub = Publication.objects.create(
        title=title, abstract="a", study_url="https://example.com",
        status=status, country_code=country_code,
    )
    Publication.objects.filter(pk=pub.pk).update(applied_at=applied_at)
    pub.refresh_from_db()
    return pub


@override_settings(SITE_URL="http://testserver")
class CollectNewContentTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.since = self.now - timedelta(days=3)

    def test_only_recent_approved_publications(self):
        recent = make_publication("Recent", self.now - timedelta(days=1))
        make_publication("Old", self.now - timedelta(days=10))
        make_publication("Pending", self.now - timedelta(days=1), status="pending")

        sections = collect_new_content(self.since)
        pub_section = next(s for s in sections if s["key"] == "publications")
        titles = [item["title"] for item in pub_section["items"]]
        self.assertEqual(titles, ["Recent"])
        self.assertIn(
            reverse("publication_detail", kwargs={"pk": recent.pk}),
            pub_section["items"][0]["url"],
        )

    def test_events_jobs_and_visits_included(self):
        event = Event.objects.create(
            title="Conf", description="d", date=self.now, location="NYC",
            status="approved",
        )
        Event.objects.filter(pk=event.pk).update(created_at=self.now - timedelta(days=1))
        Job.objects.create(
            title="Postdoc", description="d", url="https://e.com",
            deadline=self.now.date(), countries=["US"],
            created_at=self.now - timedelta(days=1), status="approved",
        )
        visit = Seminar.objects.create(countries=["US"], status="approved")
        Seminar.objects.filter(pk=visit.pk).update(created_at=self.now - timedelta(days=1))

        keys = {s["key"] for s in collect_new_content(self.since)}
        self.assertEqual(keys, {"events", "jobs", "visits"})

    def test_empty_when_nothing_new(self):
        make_publication("Old", self.now - timedelta(days=30))
        self.assertEqual(collect_new_content(self.since), [])


@override_settings(SITE_URL="http://testserver")
class SendUserDigestTests(TestCase):
    def setUp(self):
        self.now = timezone.now()

    def test_sends_and_stamps_last_digest(self):
        user = make_user()
        make_publication("Fresh Paper", self.now - timedelta(days=1))

        self.assertTrue(send_user_digest(user, now=self.now))
        self.assertEqual(len(mail.outbox), 1)

        message = mail.outbox[0]
        self.assertIn("1 new update", message.subject)
        self.assertIn("Fresh Paper", message.body)
        self.assertIn("/accounts/digest/unsubscribe/", message.body)
        html_body = message.alternatives[0][0]
        self.assertIn("Fresh Paper", html_body)

        user.profile.refresh_from_db()
        self.assertEqual(user.profile.last_digest_sent_at, self.now)

    def test_skips_when_no_new_content(self):
        user = make_user()
        make_publication("Ancient", self.now - timedelta(days=60))
        self.assertFalse(send_user_digest(user, now=self.now))
        self.assertEqual(len(mail.outbox), 0)

    def test_respects_off_preference(self):
        user = make_user(frequency=Profile.DigestFrequency.OFF)
        make_publication("Fresh", self.now - timedelta(days=1))
        self.assertFalse(send_user_digest(user, now=self.now))
        self.assertEqual(len(mail.outbox), 0)

    def test_only_content_since_last_digest(self):
        user = make_user()
        user.profile.last_digest_sent_at = self.now - timedelta(days=2)
        user.profile.save()

        make_publication("Before Last", self.now - timedelta(days=5))
        make_publication("After Last", self.now - timedelta(hours=6))

        self.assertTrue(send_user_digest(user, now=self.now))
        body = mail.outbox[0].body
        self.assertIn("After Last", body)
        self.assertNotIn("Before Last", body)


@override_settings(SITE_URL="http://testserver")
class SendDigestsCommandTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        make_publication("Command Paper", self.now - timedelta(days=1))

    def test_sends_only_to_requested_frequency(self):
        weekly = make_user("weekly@example.com", Profile.DigestFrequency.WEEKLY)
        make_user("monthly@example.com", Profile.DigestFrequency.MONTHLY)
        make_user("off@example.com", Profile.DigestFrequency.OFF)

        call_command("send_digests", "--frequency", "weekly")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [weekly.email])

    def test_dry_run_sends_nothing(self):
        make_user("weekly@example.com", Profile.DigestFrequency.WEEKLY)
        call_command("send_digests", "--frequency", "weekly", "--dry-run")
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(
            CustomUser.objects.get(email="weekly@example.com").profile.last_digest_sent_at
        )


class UnsubscribeTests(TestCase):
    def test_token_roundtrip(self):
        user = make_user()
        token = make_unsubscribe_token(user)
        self.assertEqual(read_unsubscribe_token(token), user.pk)

    def test_invalid_token_returns_none(self):
        self.assertIsNone(read_unsubscribe_token("not-a-real-token"))

    def test_unsubscribe_view_disables_digest(self):
        user = make_user()
        token = make_unsubscribe_token(user)
        response = self.client.get(
            reverse("digest_unsubscribe", kwargs={"token": token})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["success"])
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.digest_frequency, Profile.DigestFrequency.OFF)

    def test_unsubscribe_view_invalid_token(self):
        response = self.client.get(
            reverse("digest_unsubscribe", kwargs={"token": "bogus"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["success"])
