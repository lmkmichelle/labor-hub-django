import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from PyPDF2 import PdfReader
from reportlab.pdfgen import canvas

from accounts.models import CustomUser
from publications.models import Author, Publication
from publications.utils import set_ordered_authors


def make_pdf_bytes(text="original body"):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 700, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def make_user(email="author@example.com", first_name="Jane", last_name="Doe"):
    return CustomUser.objects.create_user(
        email=email, password="pass12345",
        first_name=first_name, last_name=last_name, is_active=True,
    )


def make_admin():
    return CustomUser.objects.create_user(
        email="admin@example.com", password="pass12345",
        first_name="Ada", last_name="Min", role=CustomUser.Role.ADMIN,
        is_active=True,
    )


def make_publication(**overrides):
    fields = dict(
        title="A Study",
        abstract="Abstract text.",
    )
    fields.update(overrides)
    return Publication.objects.create(**fields)


class AuthorModelTests(TestCase):
    def test_str_uses_user_full_name_when_linked(self):
        user = make_user()
        author = Author.objects.create(user=user, name="ignored")
        self.assertEqual(str(author), "Jane Doe")

    def test_str_uses_name_when_anonymous(self):
        author = Author.objects.create(user=None, name="Anon Author")
        self.assertEqual(str(author), "Anon Author")

    def test_unique_together_user_and_name(self):
        user = make_user()
        Author.objects.create(user=user, name="Jane Doe")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Author.objects.create(user=user, name="Jane Doe")


class OrderedAuthorsTests(TestCase):
    """Regression: authors previously had no persisted order at all --
    publication.authors.set(...) and authors.all() are both order-blind."""

    def test_ordered_authors_reflects_the_order_saved(self):
        publication = make_publication()
        author_a = Author.objects.create(user=None, name="Author A")
        author_b = Author.objects.create(user=None, name="Author B")

        set_ordered_authors(publication, [author_b, author_a])
        self.assertEqual(publication.ordered_authors, [author_b, author_a])

        # Editing to a new order (e.g. via the authors field's move up/down
        # buttons) persists the new order, not the original one.
        set_ordered_authors(publication, [author_a, author_b])
        self.assertEqual(publication.ordered_authors, [author_a, author_b])

    def test_a_duplicate_author_keeps_only_its_first_position(self):
        publication = make_publication()
        author = Author.objects.create(user=None, name="Author A")
        other = Author.objects.create(user=None, name="Author B")

        set_ordered_authors(publication, [author, other, author])
        self.assertEqual(publication.ordered_authors, [author, other])

    def test_cover_and_bibtex_use_the_saved_order(self):
        publication = make_publication(discussion_paper_number=1)
        publication.pdf_original.save(
            "o.pdf", SimpleUploadedFile("o.pdf", make_pdf_bytes()), save=True,
        )
        author_z = Author.objects.create(user=None, name="Zelda Zed")
        author_a = Author.objects.create(user=None, name="Amy Abe")
        set_ordered_authors(publication, [author_z, author_a])

        publication.rebuild_covered_pdf()
        publication.refresh_from_db()
        with publication.pdf.open('rb') as f:
            text = PdfReader(f).pages[0].extract_text()
        self.assertIn("ZELDA ZED AND AMY ABE", text.upper())


class PublicationModelTests(TestCase):
    def test_str_returns_title(self):
        publication = make_publication(title="Labor Markets")
        self.assertEqual(str(publication), "Labor Markets")

    def test_formatted_date_uses_the_submission_timestamp(self):
        publication = make_publication()
        self.assertEqual(
            publication.formatted_date(),
            f"{publication.applied_at:%Y-%m-%d}")

    def test_topic_defaults_to_an_empty_list(self):
        self.assertEqual(make_publication().topic, [])

    def test_approve_transitions_from_pending(self):
        admin = make_admin()
        publication = make_publication()
        publication.approve(admin)
        publication.refresh_from_db()
        self.assertEqual(publication.status, "approved")
        self.assertEqual(publication.reviewed_by, admin)
        self.assertIsNotNone(publication.reviewed_at)

    def test_approve_non_pending_raises(self):
        admin = make_admin()
        publication = make_publication(status="approved")
        with self.assertRaises(ValueError):
            publication.approve(admin)

    def test_reject_transitions_from_pending(self):
        admin = make_admin()
        publication = make_publication()
        publication.reject(admin)
        publication.refresh_from_db()
        self.assertEqual(publication.status, "rejected")
        self.assertEqual(publication.reviewed_by, admin)

    def test_reject_non_pending_raises(self):
        admin = make_admin()
        publication = make_publication(status="rejected")
        with self.assertRaises(ValueError):
            publication.reject(admin)

    def test_download_count_defaults_to_zero(self):
        self.assertEqual(make_publication().download_count, 0)

    def test_record_download_increments_by_one(self):
        publication = make_publication()
        publication.record_download()
        publication.record_download()
        self.assertEqual(publication.download_count, 2)
        publication.refresh_from_db()
        self.assertEqual(publication.download_count, 2)


class DiscussionPaperNumberTests(TestCase):
    def test_approving_assigns_sequential_numbers(self):
        admin = make_admin()
        first = make_publication(title="First")
        second = make_publication(title="Second")

        first.approve(admin)
        second.approve(admin)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.discussion_paper_number, 1)
        self.assertEqual(second.discussion_paper_number, 2)

    def test_approving_twice_does_not_renumber(self):
        admin = make_admin()
        publication = make_publication()
        publication.approve(admin)
        original_number = publication.discussion_paper_number

        # A second approve() on an already-approved paper raises (status is
        # no longer pending) before touching the number at all.
        with self.assertRaises(ValueError):
            publication.approve(admin)
        publication.refresh_from_db()
        self.assertEqual(publication.discussion_paper_number, original_number)

    def test_example_papers_are_never_numbered(self):
        admin = make_admin()
        publication = make_publication(is_example=True)
        publication.approve(admin)
        publication.refresh_from_db()
        self.assertIsNone(publication.discussion_paper_number)

    def test_example_papers_do_not_consume_a_slot(self):
        admin = make_admin()
        make_publication(is_example=True).approve(admin)
        real = make_publication()
        real.approve(admin)
        real.refresh_from_db()
        self.assertEqual(real.discussion_paper_number, 1)

    def test_regular_paper_display_number_is_plain(self):
        admin = make_admin()
        publication = make_publication()
        publication.approve(admin)
        publication.refresh_from_db()
        self.assertEqual(publication.display_number, "1")


class JobMarketPaperNumberTests(TestCase):
    """Job-market papers get their own independent "J" series (item 16),
    separate from the regular discussion_paper_number series."""

    def test_job_market_papers_get_their_own_sequence_starting_at_1(self):
        admin = make_admin()
        first = make_publication(title="First JM", is_job_market=True)
        second = make_publication(title="Second JM", is_job_market=True)

        first.approve(admin)
        second.approve(admin)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.job_market_paper_number, 1)
        self.assertEqual(second.job_market_paper_number, 2)
        self.assertIsNone(first.discussion_paper_number)
        self.assertIsNone(second.discussion_paper_number)

    def test_job_market_series_is_independent_of_the_regular_series(self):
        admin = make_admin()
        regular = make_publication(title="Regular")
        jm = make_publication(title="JM", is_job_market=True)

        regular.approve(admin)
        jm.approve(admin)

        regular.refresh_from_db()
        jm.refresh_from_db()
        # The JM paper is the first job-market paper, so J1 -- regardless of
        # how many regular papers have already been numbered.
        self.assertEqual(regular.discussion_paper_number, 1)
        self.assertEqual(jm.job_market_paper_number, 1)
        self.assertIsNone(jm.discussion_paper_number)

    def test_job_market_paper_display_number_has_a_j_prefix(self):
        admin = make_admin()
        publication = make_publication(is_job_market=True)
        publication.approve(admin)
        publication.refresh_from_db()
        self.assertEqual(publication.display_number, "J1")

    def test_example_job_market_papers_are_never_numbered(self):
        admin = make_admin()
        publication = make_publication(is_job_market=True, is_example=True)
        publication.approve(admin)
        publication.refresh_from_db()
        self.assertIsNone(publication.job_market_paper_number)


class RebuildCoveredPdfTests(TestCase):
    def _numbered_publication_with_upload(self, title="A Study"):
        publication = make_publication(title=title)
        publication.pdf_original.save(
            "original.pdf", SimpleUploadedFile("original.pdf", make_pdf_bytes()), save=True,
        )
        publication.discussion_paper_number = 1
        publication.save(update_fields=["discussion_paper_number"])
        return publication

    def test_noop_without_an_upload(self):
        publication = make_publication()
        publication.discussion_paper_number = 1
        publication.save(update_fields=["discussion_paper_number"])
        publication.rebuild_covered_pdf()
        publication.refresh_from_db()
        self.assertFalse(publication.pdf)

    def test_noop_without_a_number(self):
        publication = make_publication()
        publication.pdf_original.save(
            "o.pdf", SimpleUploadedFile("o.pdf", make_pdf_bytes()), save=True,
        )
        publication.rebuild_covered_pdf()
        publication.refresh_from_db()
        self.assertFalse(publication.pdf)

    def test_builds_a_two_page_pdf_from_a_one_page_original(self):
        publication = self._numbered_publication_with_upload()
        publication.rebuild_covered_pdf()
        publication.refresh_from_db()
        with publication.pdf.open('rb') as f:
            reader = PdfReader(f)
            self.assertEqual(len(reader.pages), 2)
            self.assertIn("original body", reader.pages[1].extract_text())

    def test_rebuilding_twice_stays_at_two_pages(self):
        """Regression: rebuild must read pdf_original, never the already
        -covered pdf, or a second rebuild stacks a second cover."""
        publication = self._numbered_publication_with_upload()
        publication.rebuild_covered_pdf()
        publication.rebuild_covered_pdf()
        publication.refresh_from_db()
        with publication.pdf.open('rb') as f:
            self.assertEqual(len(PdfReader(f).pages), 2)

    def test_rebuild_picks_up_a_changed_title(self):
        publication = self._numbered_publication_with_upload(title="Old Title")
        publication.rebuild_covered_pdf()
        publication.title = "New Title"
        publication.save(update_fields=["title"])
        publication.rebuild_covered_pdf()
        publication.refresh_from_db()
        with publication.pdf.open('rb') as f:
            reader = PdfReader(f)
            self.assertEqual(len(reader.pages), 2)
            self.assertIn("NEW TITLE", reader.pages[0].extract_text())

    def test_job_market_paper_uses_its_own_series_and_advisor_line(self):
        advisor = make_user(
            email="advisor@example.com", first_name="Ada", last_name="Visor")
        publication = make_publication(
            is_job_market=True, jm_advisor=advisor,
            job_market_paper_number=3,
        )
        publication.pdf_original.save(
            "o.pdf", SimpleUploadedFile("o.pdf", make_pdf_bytes()), save=True,
        )
        publication.rebuild_covered_pdf()
        publication.refresh_from_db()

        self.assertTrue(publication.pdf.name.startswith("publications/pdf/JMP3-"))
        with publication.pdf.open('rb') as f:
            text = PdfReader(f).pages[0].extract_text()
        self.assertIn("Job Market Paper Series No. 3", text)
        self.assertIn("Advisor: Ada Visor", text)
        self.assertNotIn("Discussion Paper", text)

    def test_job_market_paper_without_an_advisor_has_no_advisor_line(self):
        publication = make_publication(
            is_job_market=True, job_market_paper_number=4,
        )
        publication.pdf_original.save(
            "o.pdf", SimpleUploadedFile("o.pdf", make_pdf_bytes()), save=True,
        )
        publication.rebuild_covered_pdf()
        publication.refresh_from_db()
        with publication.pdf.open('rb') as f:
            text = PdfReader(f).pages[0].extract_text()
        self.assertNotIn("Advisor:", text)


class ApprovePdfLifecycleTests(TestCase):
    def test_approving_a_paper_with_no_upload_succeeds(self):
        admin = make_admin()
        publication = make_publication()
        publication.approve(admin)
        publication.refresh_from_db()
        self.assertEqual(publication.status, "approved")
        self.assertIsNotNone(publication.discussion_paper_number)
        self.assertFalse(publication.pdf)

    def test_approving_builds_the_cover(self):
        admin = make_admin()
        publication = make_publication()
        publication.pdf_original.save(
            "o.pdf", SimpleUploadedFile("o.pdf", make_pdf_bytes()), save=True,
        )
        publication.approve(admin)
        publication.refresh_from_db()
        with publication.pdf.open('rb') as f:
            self.assertEqual(len(PdfReader(f).pages), 2)

    def test_flipping_status_in_the_admin_change_form_also_builds_the_cover(self):
        """Regression: `status` is directly editable on the change form (not
        just via the Approve button); saving that must still route through
        approve() -- and its cover-building side effect -- not a raw save()."""
        admin = CustomUser.objects.create_superuser(
            email="super@example.com", password="pass12345",
            first_name="Sup", last_name="Er",
        )
        publication = make_publication()
        publication.pdf_original.save(
            "o.pdf", SimpleUploadedFile("o.pdf", make_pdf_bytes()), save=True,
        )
        author = Author.objects.create(user=None, name="An Author")
        publication.authors.set([author])
        self.client.force_login(admin)
        data = {
            "title": publication.title, "abstract": publication.abstract,
            "country_code": "", "topic": "[]", "is_job_market": "",
            "status": "approved", "admin_notes": "",
            "author_links-TOTAL_FORMS": "1",
            "author_links-INITIAL_FORMS": "1",
            "author_links-MIN_NUM_FORMS": "0",
            "author_links-MAX_NUM_FORMS": "1000",
            "author_links-0-id": str(publication.author_links.get().pk),
            "author_links-0-publication": str(publication.pk),
            "author_links-0-author": str(author.pk),
            "author_links-0-position": "0",
        }
        response = self.client.post(
            reverse("admin:publications_publication_change", args=[publication.pk]), data,
        )
        errors = (
            response.context["adminform"].form.errors
            if response.status_code == 200 else None
        )
        self.assertEqual(response.status_code, 302, errors)

        publication.refresh_from_db()
        self.assertEqual(publication.status, "approved")
        self.assertEqual(publication.reviewed_by, admin)
        self.assertIsNotNone(publication.discussion_paper_number)
        with publication.pdf.open('rb') as f:
            self.assertEqual(len(PdfReader(f).pages), 2)
