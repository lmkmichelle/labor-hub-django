"""Tests for publications.covers, the ReportLab port of Cover_page_DP.tex."""
import io

from django.test import SimpleTestCase
from PyPDF2 import PdfReader
from reportlab.pdfgen import canvas

from publications.covers import build_covered_pdf, format_authors, render_cover_page


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
