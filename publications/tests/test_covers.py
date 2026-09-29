"""Tests for publications.covers, the ReportLab port of Cover_page_DP.tex."""
import io

from django.test import SimpleTestCase
from PyPDF2 import PdfReader
from reportlab.lib.colors import black
from reportlab.pdfgen import canvas

from publications.covers import (
    CARNELIAN, build_covered_pdf, format_authors, render_cover_page,
)


def _make_pdf(pages):
    """A minimal N-page PDF with the given per-page text, for merge tests."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for text in pages:
        c.drawString(100, 700, text)
        c.showPage()
    c.save()
    return buf.getvalue()


class FormatAuthorsTests(SimpleTestCase):
    def test_single_author(self):
        self.assertEqual(format_authors(['Ada Lovelace']), 'Ada Lovelace')

    def test_two_authors(self):
        self.assertEqual(format_authors(['A', 'B']), 'A and B')

    def test_three_or_more_authors(self):
        self.assertEqual(format_authors(['A', 'B', 'C']), 'A, B, and C')
        self.assertEqual(format_authors(['A', 'B', 'C', 'D']), 'A, B, C, and D')

    def test_empty_list(self):
        self.assertEqual(format_authors([]), '')


class RenderCoverPageTests(SimpleTestCase):
    def test_single_page_with_expected_text(self):
        data = render_cover_page(7, 'A Study of Labor Markets', ['Jane Doe'])
        reader = PdfReader(io.BytesIO(data))
        self.assertEqual(len(reader.pages), 1)
        text = reader.pages[0].extract_text()
        self.assertIn('Discussion Paper No. 7', text)
        self.assertIn('A STUDY OF LABOR MARKETS', text)  # \MakeUppercase
        self.assertIn('Jane Doe', text)

    def test_number_renders_as_given(self):
        """render_cover_page interpolates whatever string it's given -- the
        "J" prefix (or lack of it) is entirely the caller's decision; see
        Publication.rebuild_covered_pdf for the regular vs. job-market
        series' actual formatting."""
        data = render_cover_page("J3", 'A Study of Labor Markets', ['Jane Doe'])
        text = PdfReader(io.BytesIO(data)).pages[0].extract_text()
        self.assertIn('Discussion Paper No. J3', text)

    def test_long_title_still_fits_one_page(self):
        long_title = 'A Very Long Discussion Paper Title About ' + ' '.join(
            ['Labor', 'Markets', 'And', 'Networks'] * 10
        )
        data = render_cover_page(
            1, long_title,
            ['Author One', 'Author Two', 'Author Three', 'Author Four', 'Author Five'],
        )
        reader = PdfReader(io.BytesIO(data))
        self.assertEqual(len(reader.pages), 1)

    def test_non_ascii_author_name_renders(self):
        """A non-ASCII name round-trips only if the embedded TTF -- not a
        built-in Latin-1 font -- is actually being used."""
        data = render_cover_page(1, 'Title', ['Michèle Belot'])
        reader = PdfReader(io.BytesIO(data))
        self.assertIn('Michèle Belot', reader.pages[0].extract_text())


class JobMarketPaperOverlayTests(SimpleTestCase):
    """A job-market paper reuses the exact same backdrop/layout as a regular
    discussion paper -- only the overlay differs, per Jason's clarification:
    black instead of Carnelian text, the "Job Market Paper Series" label, and
    an "Advisor: <name>" line whenever one is named."""

    def test_series_label_and_advisor_line(self):
        data = render_cover_page(
            3, 'A Study of Labor Markets', ['Jane Doe'],
            series_label='Job Market Paper Series', advisor='Jane Advisor',
            text_color=black,
        )
        text = PdfReader(io.BytesIO(data)).pages[0].extract_text()
        self.assertIn('Job Market Paper Series No. 3', text)
        self.assertNotIn('Discussion Paper', text)
        self.assertIn('Advisor: Jane Advisor', text)

    def test_no_advisor_line_when_advisor_omitted(self):
        data = render_cover_page(
            3, 'A Study of Labor Markets', ['Jane Doe'],
            series_label='Job Market Paper Series', text_color=black,
        )
        text = PdfReader(io.BytesIO(data)).pages[0].extract_text()
        self.assertNotIn('Advisor:', text)

    def test_regular_discussion_paper_defaults_are_unchanged(self):
        """No keyword arguments -> identical to the pre-JMP-overlay behavior."""
        data = render_cover_page(7, 'A Study of Labor Markets', ['Jane Doe'])
        text = PdfReader(io.BytesIO(data)).pages[0].extract_text()
        self.assertIn('Discussion Paper No. 7', text)
        self.assertNotIn('Job Market Paper Series', text)
        self.assertNotIn('Advisor:', text)

    def test_title_fill_color_is_black_for_a_job_market_paper(self):
        """Inspect the overlay's own content stream (not the merged/backdrop
        page, whose artwork has its own fill colors) for the black fill set
        before the title is drawn, and Carnelian's absence."""
        import publications.covers as covers

        overlay_buffer = io.BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=covers.letter)
        covers._draw_centered_block(
            c, 'TITLE', covers.TITLE_X, covers.TITLE_Y_CENTER, covers.TITLE_WIDTH,
            {'fontName': covers.FONT_BOLD, 'textColor': black},
            covers.TITLE_FONT_SIZE, covers.TITLE_MIN_FONT_SIZE,
        )
        c.showPage()
        c.save()
        overlay_buffer.seek(0)
        content = PdfReader(overlay_buffer).pages[0].get_contents().get_data()
        self.assertIn(b'0 0 0 rg', content)  # black fill (RGB 0,0,0)
        carnelian_r, carnelian_g, carnelian_b = CARNELIAN.rgb()
        carnelian_op = f'{carnelian_r:g} {carnelian_g:g} {carnelian_b:g} rg'.encode()
        self.assertNotIn(carnelian_op, content)


class BuildCoveredPdfTests(SimpleTestCase):
    def test_prepends_one_page_and_keeps_original_intact(self):
        original = _make_pdf(['page one text', 'page two text'])
        combined = build_covered_pdf(original, 4, 'Some Paper', ['Author A'])
        reader = PdfReader(io.BytesIO(combined))
        self.assertEqual(len(reader.pages), 3)
        self.assertIn('page one text', reader.pages[1].extract_text())
        self.assertIn('page two text', reader.pages[2].extract_text())

    def test_sets_pdf_metadata(self):
        original = _make_pdf(['body'])
        combined = build_covered_pdf(original, 2, 'The Title', ['A', 'B'])
        reader = PdfReader(io.BytesIO(combined))
        self.assertEqual(reader.metadata.get('/Title'), 'The Title')
        self.assertEqual(reader.metadata.get('/Author'), 'A and B')
        self.assertEqual(reader.metadata.get('/Subject'), 'Discussion Paper No. 2')
        self.assertEqual(reader.metadata.get('/Keywords'), 'discussion paper')
