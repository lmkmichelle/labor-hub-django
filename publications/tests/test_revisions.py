import json

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


def pick(paper):
    """What Tagify submits after choosing ``paper`` in the revision picker."""
    return json.dumps([{"value": f"[{paper.display_number}] {paper.title}", "id": paper.pk}])


class RevisionFormTests(TestCase):
    def _form(self, user, paper=None, **data):
        post = create_post_data(paper_type="revision", **data)
        if paper is not None:
            post["revision_of_input"] = pick(paper)
        return PublicationForm(post, user=user)

    def test_author_can_revise_their_paper(self):
        original, user = numbered_paper(323)
        form = self._form(user, original)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form._original, original)

    def test_submitter_who_is_not_listed_as_an_author_can_revise(self):
        original, _ = numbered_paper(323)
        submitter = make_user(email="sub@example.com", first_name="Sub", last_name="Mitter")
        Publication.objects.filter(pk=original.pk).update(submitted_by=submitter)
        form = self._form(submitter, original)
        self.assertTrue(form.is_valid(), form.errors)

    def test_someone_elses_paper_is_rejected(self):
        original, _ = numbered_paper(323)
        stranger = make_user(email="x@example.com", first_name="Not", last_name="Author")
        form = self._form(stranger, original)
        self.assertFalse(form.is_valid())
        self.assertIn("revision_of_input", form.errors)

    def test_a_forged_id_for_a_paper_not_in_the_picker_is_rejected(self):
        original, _ = numbered_paper(323)
        stranger = make_user(email="x@example.com", first_name="Not", last_name="Author")
        post = create_post_data(paper_type="revision", revision_of_input=str(original.pk))
        self.assertFalse(PublicationForm(post, user=stranger).is_valid())

    def test_unpublished_paper_is_rejected(self):
        original, user = numbered_paper(323)
        Publication.objects.filter(pk=original.pk).update(status="pending")
        original.refresh_from_db()
        self.assertFalse(self._form(user, original).is_valid())

    def test_choosing_revision_without_a_paper_is_rejected(self):
        _, user = numbered_paper(323)
        form = self._form(user)
        self.assertFalse(form.is_valid())
        self.assertIn("revision_of_input", form.errors)

    def test_a_revision_inherits_the_job_market_series_and_advisor(self):
        advisor = make_user(email="adv@example.com", first_name="Ad", last_name="Visor")
        user = make_user()
        original = make_publication(
            status="approved", is_job_market=True, job_market_paper_number=3, jm_advisor=advisor)
        original.authors.add(Author.objects.get_or_create(user=user, name="Jane Doe")[0])
        form = self._form(user, original)
        self.assertTrue(form.is_valid(), form.errors)
        revision = form.save()
        self.assertTrue(revision.is_job_market)
        self.assertEqual(revision.jm_advisor, advisor)

    def test_submitting_creates_a_linked_pending_revision(self):
        original, user = numbered_paper(323)
        self.client.force_login(user)
        self.client.post(reverse("submit_paper"), create_post_data(
            paper_type="revision", revision_of_input=pick(original)))
        revision = Publication.objects.get(title="New Paper")
        self.assertEqual(revision.revision_of, original)
        self.assertEqual(revision.status, "pending")


class RevisablePapersTests(TestCase):
    def test_lists_only_published_originals_the_user_submitted_or_authored(self):
        original, user = numbered_paper(323)
        make_revision(original)                       # a revision is not offered
        pending = make_publication(status="pending")  # not published yet
        pending.authors.add(Author.objects.get(user=user))
        other = make_publication(status="approved", discussion_paper_number=400)
        submitted = make_publication(status="approved", discussion_paper_number=401,
                                     submitted_by=user)
        self.assertEqual(set(Publication.revisable_by(user)), {original, submitted})
        self.assertNotIn(other, Publication.revisable_by(user))

    def test_matches_an_author_typed_in_under_the_users_full_name(self):
        paper = make_publication(status="approved", discussion_paper_number=500)
        paper.authors.add(Author.objects.create(user=None, name="Jane Doe"))
        self.assertEqual(list(Publication.revisable_by(make_user())), [paper])

    def test_anonymous_user_gets_nothing(self):
        from django.contrib.auth.models import AnonymousUser
        numbered_paper(323)
        self.assertFalse(Publication.revisable_by(AnonymousUser()).exists())


class SubmitPageTests(TestCase):
    def test_shows_the_three_type_cards_and_the_users_papers(self):
        original, user = numbered_paper(323, title="Wages and Work")
        self.client.force_login(user)
        page = self.client.get(reverse("submit_paper"))
        for label in ("Discussion paper", "Job market paper", "Revision of a previous paper"):
            self.assertContains(page, label)
        self.assertContains(page, 'id="revision-papers-data"')
        self.assertContains(page, "[323] Wages and Work")
        self.assertNotContains(page, "\\u2014")
        self.assertNotContains(page, "You have no published papers to revise yet.")

    def test_papers_the_user_cannot_revise_are_not_in_the_page(self):
        numbered_paper(323, title="Someone Else's Paper")
        stranger = make_user(email="x@example.com", first_name="Not", last_name="Author")
        self.client.force_login(stranger)
        page = self.client.get(reverse("submit_paper"))
        self.assertNotContains(page, "Someone Else")
        self.assertContains(page, "You have no published papers to revise yet.")
        self.assertContains(page, "disabled")

    def test_editing_offers_no_revision_card(self):
        paper, user = numbered_paper(323)
        self.client.force_login(user)
        page = self.client.get(reverse("edit_publication", kwargs={"pk": paper.pk}))
        self.assertNotContains(page, 'value="revision"')
        self.assertContains(page, 'value="job_market"')
        self.assertContains(page, "checked")


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
        self.assertNotIn("revision_of_input", fields)
        self.assertEqual([c[0] for c in fields["paper_type"].choices], ["discussion", "job_market"])

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


class EditingKeepsTheTypeTests(TestCase):
    def test_editing_a_job_market_paper_keeps_its_type_and_advisor(self):
        advisor = make_user(email="adv@example.com", first_name="Ad", last_name="Visor")
        user = make_user()
        paper = make_publication(status="pending", is_job_market=True, jm_advisor=advisor)
        paper.authors.add(Author.objects.get_or_create(user=user, name="Jane Doe")[0])
        form = PublicationForm(
            {k: v for k, v in create_post_data(jm_advisor=advisor.pk).items() if k != "paper_type"},
            instance=paper, user=user)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertTrue(saved.is_job_market)
        self.assertEqual(saved.jm_advisor, advisor)

    def test_editing_a_revision_keeps_its_series_and_has_no_type_choice(self):
        original, user = numbered_paper(323)
        revision = make_revision(original)
        form = PublicationForm(instance=revision, user=user)
        self.assertNotIn("paper_type", form.fields)
        edited = PublicationForm(
            {k: v for k, v in create_post_data(title="Retitled").items() if k != "paper_type"},
            instance=revision, user=user)
        self.assertTrue(edited.is_valid(), edited.errors)
        saved = edited.save()
        self.assertEqual(saved.revision_of, original)
        self.assertEqual(saved.is_job_market, original.is_job_market)


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
