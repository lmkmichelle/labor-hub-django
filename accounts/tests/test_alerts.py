from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.alerts import (
    collect_alert_matches,
    make_unsubscribe_token,
    read_unsubscribe_token,
    send_user_alerts,
)
from core.tests.email_assertions import assert_has_html_alternative_with_logo
from accounts.models import CustomUser, Profile
from publications.models import Publication
from seminars.models import Seminar, University


def make_user(email="alerts@example.com", topics=None, countries=None, universities=None):
    user = CustomUser.objects.create_user(
        email=email, password="pass12345", first_name="Al", last_name="Erts",
        is_active=True,
    )
    user.profile.alert_topics = topics or []
    user.profile.alert_countries = countries or []
    user.profile.alert_universities = universities or []
    user.profile.save()
    return user


def make_publication(title, applied_at, status="approved", topic=None):
    pub = Publication.objects.create(title=title, status=status, topic=topic or [])
    Publication.objects.filter(pk=pub.pk).update(applied_at=applied_at)
    pub.refresh_from_db()
    return pub


def make_visit(title, created_at, status="approved", countries=None, university=None):
    visit = Seminar.objects.create(
        visitor_name=title, university_name="Some University",
        status=status, countries=countries or [], university=university,
    )
    Seminar.objects.filter(pk=visit.pk).update(created_at=created_at)
    visit.refresh_from_db()
    return visit


@override_settings(SITE_URL="http://testserver")
class CollectAlertMatchesTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.since = self.now - timedelta(days=3)

    def test_matches_a_subscribed_topic(self):
        profile = make_user(topics=["Labor Supply"]).profile
        make_publication(
            "Matches", self.now - timedelta(days=1), topic=["Labor Supply"])
        make_publication(
            "No Match", self.now - timedelta(days=1), topic=["Migration"])

        sections = collect_alert_matches(profile, self.since)
        pub_section = next(s for s in sections if s["key"] == "publications")
        titles = [item["title"] for item in pub_section["items"]]
        self.assertEqual(titles, ["Matches"])

    def test_publications_before_since_are_excluded(self):
        profile = make_user(topics=["Labor Supply"]).profile
        make_publication(
            "Old", self.now - timedelta(days=10), topic=["Labor Supply"])
        sections = collect_alert_matches(profile, self.since)
        self.assertFalse(any(s["key"] == "publications" for s in sections))

    def test_pending_publications_are_excluded(self):
        profile = make_user(topics=["Labor Supply"]).profile
        make_publication(
            "Pending", self.now - timedelta(days=1), status="pending",
            topic=["Labor Supply"])
        sections = collect_alert_matches(profile, self.since)
        self.assertFalse(any(s["key"] == "publications" for s in sections))

    def test_no_topics_subscribed_means_no_publications_section(self):
        profile = make_user(topics=[]).profile
        make_publication(
            "Anything", self.now - timedelta(days=1), topic=["Labor Supply"])
        sections = collect_alert_matches(profile, self.since)
        self.assertFalse(any(s["key"] == "publications" for s in sections))

    def test_matches_a_subscribed_country(self):
        profile = make_user(countries=["DE"]).profile
        make_visit("Matches", self.now - timedelta(days=1), countries=["DE"])
        make_visit("No Match", self.now - timedelta(days=1), countries=["FR"])

        sections = collect_alert_matches(profile, self.since)
        visit_section = next(s for s in sections if s["key"] == "visits")
        titles = [item["title"] for item in visit_section["items"]]
        self.assertEqual(len(titles), 1)
        self.assertIn("Matches", titles[0])

    def test_item_submitted_before_since_but_approved_after_is_included(self):
        profile = make_user(topics=["Labor Supply"], countries=["DE"]).profile
        pub = make_publication(
            "Late", self.now - timedelta(days=5), topic=["Labor Supply"])
        visit = make_visit("Late visit", self.now - timedelta(days=5), countries=["DE"])
        Publication.objects.filter(pk=pub.pk).update(reviewed_at=self.now - timedelta(days=1))
        Seminar.objects.filter(pk=visit.pk).update(reviewed_at=self.now - timedelta(days=1))

        keys = {s["key"] for s in collect_alert_matches(profile, self.since)}
        self.assertEqual(keys, {"publications", "visits"})

    def test_item_approved_before_since_is_not_repeated(self):
        profile = make_user(topics=["Labor Supply"]).profile
        pub = make_publication(
            "Seen", self.now - timedelta(days=1), topic=["Labor Supply"])
        Publication.objects.filter(pk=pub.pk).update(reviewed_at=self.now - timedelta(days=5))
        self.assertEqual(collect_alert_matches(profile, self.since), [])

    def test_visits_before_since_are_excluded(self):
        profile = make_user(countries=["DE"]).profile
        make_visit("Old", self.now - timedelta(days=10), countries=["DE"])
        sections = collect_alert_matches(profile, self.since)
        self.assertFalse(any(s["key"] == "visits" for s in sections))

    def test_pending_visits_are_excluded(self):
        profile = make_user(countries=["DE"]).profile
        make_visit(
            "Pending", self.now - timedelta(days=1), status="pending", countries=["DE"])
        sections = collect_alert_matches(profile, self.since)
        self.assertFalse(any(s["key"] == "visits" for s in sections))

    def test_matches_both_topics_and_countries(self):
        profile = make_user(topics=["Labor Supply"], countries=["DE"]).profile
        make_publication(
            "Paper", self.now - timedelta(days=1), topic=["Labor Supply"])
        make_visit("Visit", self.now - timedelta(days=1), countries=["DE"])
        sections = collect_alert_matches(profile, self.since)
        keys = {s["key"] for s in sections}
        self.assertEqual(keys, {"publications", "visits"})


@override_settings(SITE_URL="http://testserver")
class SendUserAlertsTests(TestCase):
    def setUp(self):
        self.now = timezone.now()

    def test_sends_and_stamps_last_alert(self):
        user = make_user(topics=["Labor Supply"])
        make_publication(
            "Fresh Paper", self.now - timedelta(days=1), topic=["Labor Supply"])

        self.assertTrue(send_user_alerts(user, now=self.now))
        self.assertEqual(len(mail.outbox), 1)

        message = mail.outbox[0]
        self.assertIn("1 new match", message.subject)
        self.assertIn("Fresh Paper", message.body)
        self.assertIn("/accounts/alerts/unsubscribe/", message.body)
        html_body = assert_has_html_alternative_with_logo(self, message)
        self.assertIn("Fresh Paper", html_body)

        user.profile.refresh_from_db()
        self.assertEqual(user.profile.last_alert_sent_at, self.now)

    def test_no_subscriptions_means_no_email(self):
        user = make_user()
        make_publication("Paper", self.now - timedelta(days=1), topic=["Labor Supply"])
        self.assertFalse(send_user_alerts(user, now=self.now))
        self.assertEqual(len(mail.outbox), 0)

    def test_no_matches_means_no_email(self):
        user = make_user(topics=["Migration"])
        make_publication("Paper", self.now - timedelta(days=1), topic=["Labor Supply"])
        self.assertFalse(send_user_alerts(user, now=self.now))
        self.assertEqual(len(mail.outbox), 0)

    def test_sets_list_unsubscribe_header(self):
        user = make_user(topics=["Labor Supply"])
        make_publication("Paper", self.now - timedelta(days=1), topic=["Labor Supply"])
        send_user_alerts(user, now=self.now)
        headers = mail.outbox[0].extra_headers
        self.assertIn("List-Unsubscribe", headers)
        self.assertIn("/accounts/alerts/unsubscribe/", headers["List-Unsubscribe"])

    def test_a_relay_failure_does_not_stamp_last_alert_or_raise(self):
        user = make_user(topics=["Labor Supply"])
        make_publication("Paper", self.now - timedelta(days=1), topic=["Labor Supply"])
        with mock.patch(
            "django.core.mail.EmailMultiAlternatives.send", return_value=0
        ):
            self.assertFalse(send_user_alerts(user, now=self.now))
        user.profile.refresh_from_db()
        self.assertIsNone(user.profile.last_alert_sent_at)

    def test_second_send_only_covers_content_since_the_first(self):
        user = make_user(topics=["Labor Supply"])
        make_publication(
            "First", self.now - timedelta(days=5), topic=["Labor Supply"])
        self.assertTrue(send_user_alerts(user, now=self.now - timedelta(days=4)))

        make_publication(
            "Second", self.now - timedelta(days=1), topic=["Labor Supply"])
        self.assertTrue(send_user_alerts(user, now=self.now))

        second_message = mail.outbox[-1]
        self.assertIn("Second", second_message.body)
        self.assertNotIn("First", second_message.body)


@override_settings(SITE_URL="http://testserver")
class SendAlertsCommandTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        make_publication("Command Paper", self.now - timedelta(days=1), topic=["Labor Supply"])

    def test_sends_only_to_subscribed_users(self):
        subscribed = make_user("subscribed@example.com", topics=["Labor Supply"])
        make_user("not-subscribed@example.com")

        call_command("send_alerts")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [subscribed.email])

    def test_dry_run_sends_nothing(self):
        make_user("subscribed@example.com", topics=["Labor Supply"])
        call_command("send_alerts", "--dry-run")
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(
            CustomUser.objects.get(email="subscribed@example.com")
            .profile.last_alert_sent_at
        )

    def test_reuses_a_single_connection_across_the_cohort(self):
        make_user("a@example.com", topics=["Labor Supply"])
        make_user("b@example.com", topics=["Labor Supply"])

        with mock.patch(
            "accounts.management.commands.send_alerts.get_connection"
        ) as get_connection:
            connection = get_connection.return_value
            call_command("send_alerts")

        get_connection.assert_called_once()
        connection.open.assert_called_once()
        connection.close.assert_called_once()


class AlertsUnsubscribeTests(TestCase):
    def test_token_roundtrip(self):
        user = make_user()
        token = make_unsubscribe_token(user)
        self.assertEqual(read_unsubscribe_token(token), user.pk)

    def test_invalid_token_returns_none(self):
        self.assertIsNone(read_unsubscribe_token("not-a-real-token"))

    def test_digest_token_cannot_unsubscribe_alerts(self):
        # A separate salt from accounts.digests' token, so a digest
        # unsubscribe link can't be replayed to also clear alert prefs.
        from accounts.digests import make_unsubscribe_token as make_digest_token
        user = make_user()
        token = make_digest_token(user)
        self.assertIsNone(read_unsubscribe_token(token))

    def test_unsubscribe_view_clears_both_lists(self):
        user = make_user(topics=["Labor Supply"], countries=["DE"])
        token = make_unsubscribe_token(user)
        response = self.client.get(
            reverse("alerts_unsubscribe", kwargs={"token": token})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["success"])
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.alert_topics, [])
        self.assertEqual(user.profile.alert_countries, [])

    def test_unsubscribe_view_invalid_token(self):
        response = self.client.get(
            reverse("alerts_unsubscribe", kwargs={"token": "bogus"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["success"])


class InstitutionAlertTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.since = self.now - timedelta(days=3)
        self.lse = University.objects.create(name="LSE", country_code="GB")
        self.other = University.objects.create(name="Other U", country_code="FR")

    def _titles(self, profile):
        sections = collect_alert_matches(profile, self.since)
        return [i["title"] for s in sections if s["key"] == "visits" for i in s["items"]]

    def test_institution_only_subscriber_gets_that_institutions_visits(self):
        profile = make_user(universities=[self.lse.pk]).profile
        make_visit("At LSE", self.now - timedelta(days=1), university=self.lse)
        make_visit("At Other", self.now - timedelta(days=1), university=self.other)
        self.assertEqual(len(self._titles(profile)), 1)

    def test_country_and_institution_overlap_lists_the_visit_once(self):
        profile = make_user(countries=["GB"], universities=[self.lse.pk]).profile
        make_visit("At LSE", self.now - timedelta(days=1),
                   countries=["GB"], university=self.lse)
        self.assertEqual(len(self._titles(profile)), 1)

    def test_send_user_alerts_runs_for_institution_only_subscribers(self):
        user = make_user(universities=[self.lse.pk])
        make_visit("At LSE", self.now - timedelta(days=1), university=self.lse)
        self.assertTrue(send_user_alerts(user, now=self.now))
        self.assertEqual(len(mail.outbox), 1)


class AlertUniversitiesFormTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.lse = University.objects.create(name="LSE", country_code="GB")

    def test_saves_valid_ids_and_drops_unknown_and_duplicates(self):
        self.client.post(reverse("settings"), {
            "save_alerts": "1",
            "alert_universities": f'["{self.lse.pk}", "{self.lse.pk}", "99999", "abc"]',
        })
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.alert_universities, [self.lse.pk])

    def test_settings_page_preloads_only_saved_institutions(self):
        University.objects.bulk_create(
            University(name=f"Filler {i}", country_code="US") for i in range(30))
        self.user.profile.alert_universities = [self.lse.pk]
        self.user.profile.save()
        response = self.client.get(reverse("settings"))
        self.assertContains(response, "LSE, United Kingdom")
        self.assertNotContains(response, "Filler 1")

    def test_unsubscribe_clears_institutions_too(self):
        self.user.profile.alert_universities = [self.lse.pk]
        self.user.profile.save()
        self.client.get(reverse(
            "alerts_unsubscribe", args=[make_unsubscribe_token(self.user)]))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.alert_universities, [])
