from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from publications.citations import cite_key
from publications.forms import PublicationForm
from publications.models import Author, Publication
from publications.tests.test_views import create_post_data, make_publication, make_user


def numbered_paper(number=323, **fields):
    """An approved, numbered paper authored by Jane Doe."""
    user = fields.pop("user", None) or make_user()
    paper = make_publication(status="approved", discussion_paper_number=number, **fields)
    paper.authors.add(Author.objects.get_or_create(user=user, name="Jane Doe")[0])
    return paper, user


def make_revision(original, status="approved"):
    revision = Publication.objects.create(
        title="Revised", abstract="x", status="pending", revision_of=original,
        is_job_market=original.is_job_market)
    if status == "approved":
        revision.approve()
        revision.refresh_from_db()
    return revision


class RevisionNumberingTests(TestCase):
    def test_first_and_second_revision(self):
        original, _ = numbered_paper(323)
        first, second = make_revision(original), make_revision(original)
        self.assertEqual(first.display_number, "323.1")
        self.assertEqual(second.display_number, "323.2")

    def test_revisions_do_not_consume_a_series_slot(self):
        original, _ = numbered_paper(323)
        make_revision(original)
        later = make_publication(status="pending")
        later.approve()
        self.assertEqual(later.discussion_paper_number, 324)

    def test_job_market_series(self):
        original = make_publication(status="approved", is_job_market=True,
                                    job_market_paper_number=3)
        self.assertEqual(make_revision(original).display_number, "J3.1")

    def test_pending_revision_has_no_number_yet(self):
        original, _ = numbered_paper(323)
        self.assertIsNone(make_revision(original, status="pending").display_number)

    def test_cite_key_keeps_the_revision(self):
        original, _ = numbered_paper(323)
        self.assertEqual(cite_key(make_revision(original)), "LaborHubDP323.1")


class RevisionFormTests(TestCase):
    def _form(self, user, **data):
        post = create_post_data(is_revision="on", **data)
        return PublicationForm(post, user=user)

    def test_author_can_revise_by_original_number(self):
        original, user = numbered_paper(323)
        form = self._form(user, previous_number="323")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form._original, original)

    def test_revision_number_resolves_to_the_original(self):
        original, user = numbered_paper(323)
        form = self._form(user, previous_number="323.1")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form._original, original)

    def test_unknown_number_is_rejected(self):
        _, user = numbered_paper(323)
        form = self._form(user, previous_number="999")
        self.assertFalse(form.is_valid())
        self.assertIn("previous_number", form.errors)

    def test_non_author_is_rejected(self):
        numbered_paper(323)
        stranger = make_user(email="x@example.com", first_name="Not", last_name="Author")
        form = self._form(stranger, previous_number="323")
        self.assertFalse(form.is_valid())
        self.assertIn("previous_number", form.errors)

    def test_unpublished_original_is_rejected(self):
        original, user = numbered_paper(323)
        Publication.objects.filter(pk=original.pk).update(status="pending")
        form = self._form(user, previous_number="323")
        self.assertFalse(form.is_valid())

    def test_ticking_without_a_number_is_rejected(self):
        _, user = numbered_paper(323)
        self.assertFalse(self._form(user, previous_number="").is_valid())

    def test_submitting_creates_a_linked_pending_revision(self):
        original, user = numbered_paper(323)
        self.client.force_login(user)
        self.client.post(reverse("submit_paper"), create_post_data(
            is_revision="on", previous_number="323"))
        revision = Publication.objects.get(title="New Paper")
        self.assertEqual(revision.revision_of, original)
        self.assertEqual(revision.status, "pending")


class PublishedPaperEditingTests(TestCase):
    def test_published_paper_edit_form_has_no_pdf(self):
        paper, user = numbered_paper(323)
        self.assertNotIn("pdf", PublicationForm(instance=paper, user=user).fields)

    def test_pending_paper_edit_form_keeps_the_pdf(self):
        user = make_user()
        paper = make_publication(status="pending")
        self.assertIn("pdf", PublicationForm(instance=paper, user=user).fields)

    def test_edit_form_has_no_revision_fields(self):
        paper, user = numbered_paper(323)
        fields = PublicationForm(instance=paper, user=user).fields
        self.assertNotIn("is_revision", fields)

    def test_posted_pdf_is_ignored_on_a_published_paper(self):
        paper, user = numbered_paper(323)
        self.client.force_login(user)
        self.client.post(
            reverse("edit_publication", kwargs={"pk": paper.pk}),
            {**create_post_data(title="Retitled"),
             "pdf": SimpleUploadedFile("new.pdf", b"%PDF-1.4 new", "application/pdf")})
        paper.refresh_from_db()
        self.assertEqual(paper.title, "Retitled")
        self.assertFalse(paper.pdf_original)
        self.assertIsNone(paper.revision_number)


class OtherVersionsTests(TestCase):
    def _url(self, paper):
        return reverse("publication_detail", kwargs={"pk": paper.pk})

    def test_original_and_revision_link_to_each_other(self):
        original, _ = numbered_paper(323)
        revision = make_revision(original)
        page = self.client.get(self._url(original))
        self.assertContains(page, "Other Versions")
        self.assertContains(page, f'href="{self._url(revision)}"')
        self.assertContains(page, "No. 323.1")
        back = self.client.get(self._url(revision))
        self.assertContains(back, f'href="{self._url(original)}"')

    def test_siblings_are_listed_but_not_the_page_itself(self):
        original, _ = numbered_paper(323)
        first, second = make_revision(original), make_revision(original)
        page = self.client.get(self._url(first))
        self.assertContains(page, "No. 323.2")
        self.assertNotContains(page, "No. 323.1:")

    def test_pending_revisions_are_hidden(self):
        original, _ = numbered_paper(323)
        make_revision(original, status="pending")
        page = self.client.get(self._url(original))
        self.assertNotContains(page, "Other Versions")

    def test_no_section_for_a_paper_with_no_versions(self):
        original, _ = numbered_paper(323)
        self.assertNotContains(self.client.get(self._url(original)), "Other Versions")
