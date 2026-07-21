from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from publications.models import Author, Publication


def make_user(email="author@example.com", first_name="Jane", last_name="Doe"):
    return CustomUser.objects.create_user(
        email=email, password="pass12345",
        first_name=first_name, last_name=last_name, is_active=True,
    )


def make_publication(status="approved", **overrides):
    fields = dict(
        title="A Study",
        abstract="Abstract text.",
        study_url="https://example.com/study",
        status=status,
    )
    fields.update(overrides)
    return Publication.objects.create(**fields)


def create_post_data(**overrides):
    data = {
        "title": "New Paper",
        "date": "2025-06-01",
        "abstract": "Some abstract.",
        "country_code": "US",
        "study_url": "https://example.com/new",
        "is_job_market": True,
        "authors_input": '[{"value":"Jane Doe"}]',
        "topic_input": "Labor",
        "keywords_input": '[{"value":"economics"}]',
    }
    data.update(overrides)
    return data


class PublicationDetailViewTests(TestCase):
    def test_approved_publication_is_visible(self):
        publication = make_publication(status="approved")
        response = self.client.get(
            reverse("publication_detail", kwargs={"pk": publication.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "publications/publication_detail.html")

    def test_pending_publication_hidden_from_anonymous(self):
        publication = make_publication(status="pending")
        response = self.client.get(
            reverse("publication_detail", kwargs={"pk": publication.pk}))
        self.assertEqual(response.status_code, 404)

    def test_pending_publication_visible_to_author(self):
        user = make_user()
        publication = make_publication(status="pending")
        publication.authors.add(Author.objects.create(user=user, name="Jane Doe"))
        self.client.force_login(user)
        response = self.client.get(
            reverse("publication_detail", kwargs={"pk": publication.pk}))
        self.assertEqual(response.status_code, 200)

    def test_abstract_preserves_line_breaks(self):
        publication = make_publication(
            status="approved",
            abstract="First paragraph.\n\nSecond paragraph.")
        response = self.client.get(
            reverse("publication_detail", kwargs={"pk": publication.pk}))
        content = response.content.decode()
        self.assertIn("<p>First paragraph.</p>", content)
        self.assertIn("<p>Second paragraph.</p>", content)


class PublicationCreateViewTests(TestCase):
    def test_get_renders_form(self):
        response = self.client.get(reverse("submit_paper"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "publications/publication_form.html")

    def test_post_creates_publication_with_authors_and_keywords(self):
        response = self.client.post(reverse("submit_paper"), create_post_data())
        self.assertRedirects(response, reverse("publications"))
        publication = Publication.objects.get(title="New Paper")
        self.assertEqual(publication.status, "pending")
        self.assertEqual(publication.topic, "Labor")
        self.assertEqual(publication.keywords, ["economics"])
        self.assertEqual(publication.authors.count(), 1)


class PublicationUpdateViewTests(TestCase):
    def test_non_author_cannot_edit(self):
        make_publication(status="approved")
        publication = Publication.objects.first()
        other = make_user(email="other@example.com", first_name="Other", last_name="User")
        self.client.force_login(other)
        response = self.client.get(
            reverse("edit_publication", kwargs={"pk": publication.pk}))
        self.assertEqual(response.status_code, 404)

    def test_author_can_edit(self):
        user = make_user()
        publication = make_publication(status="approved", title="Old Title")
        publication.authors.add(Author.objects.create(user=user, name="Jane Doe"))
        self.client.force_login(user)
        response = self.client.post(
            reverse("edit_publication", kwargs={"pk": publication.pk}),
            create_post_data(title="Updated Title"))
        self.assertRedirects(response, reverse("publications"))
        publication.refresh_from_db()
        self.assertEqual(publication.title, "Updated Title")

    def test_edit_form_renders_iso_date_and_round_trips(self):
        import datetime

        user = make_user()
        publication = make_publication(
            status="approved", date=datetime.date(2026, 7, 21))
        publication.authors.add(Author.objects.create(user=user, name="Jane Doe"))
        self.client.force_login(user)

        response = self.client.get(
            reverse("edit_publication", kwargs={"pk": publication.pk}))
        content = response.content.decode()
        # The Flowbite datepicker must be told the value is ISO so it does not
        # misparse it as mm/dd/yyyy and mangle the date.
        self.assertIn('datepicker-format="yyyy-mm-dd"', content)
        self.assertIn('value="2026-07-21"', content)

        self.client.post(
            reverse("edit_publication", kwargs={"pk": publication.pk}),
            create_post_data(date="2026-07-21"))
        publication.refresh_from_db()
        self.assertEqual(publication.date, datetime.date(2026, 7, 21))
