"""Generates the branded discussion-paper cover page and prepends it to an
uploaded PDF.

This is a Python port of ``Cover_page_DP.tex`` (the LaTeX template Jason
supplied, kept at the repo root as ``static/cover_page.zip`` for provenance).
Upsun's build container cannot install a TeX distribution (see
``.upsun/config.yaml``), so the overlay -- a full-bleed backdrop plus three
absolutely-positioned text blocks -- is drawn directly with ReportLab instead
of shelling out to ``pdflatex``.

The backdrop (``static/pdfs/cover_backdrop.pdf``) and the two Latin Modern
Sans faces the ``.tex`` selects via ``\\usepackage{lmodern}`` +
``\\renewcommand{\\familydefault}{\\sfdefault}`` are vendored under
``static/``; see ``static/fonts/README.md`` for how they were derived.
"""
import io

from django.contrib.staticfiles.finders import find as find_static
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from reportlab.lib.colors import HexColor, black
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

PAGE_WIDTH, PAGE_HEIGHT = letter  # 612 x 792 pt, matching the backdrop's letter page.

CARNELIAN = HexColor('#B31B1B')

FONT_REGULAR = 'LMSans10-Regular'
FONT_BOLD = 'LMSans10-Bold'

# Registered once at import time. A missing/unloadable TTF must fail loudly --
# a silent fallback to a built-in ReportLab font would ship the wrong typeface.
pdfmetrics.registerFont(TTFont(FONT_REGULAR, find_static('fonts/LMSans10-Regular.ttf')))
pdfmetrics.registerFont(TTFont(FONT_BOLD, find_static('fonts/LMSans10-Bold.ttf')))

# Geometry ported from Cover_page_DP.tex's \put coordinates (fractions of the
# 612x792pt letter page, eso-pic's lower-left origin), calibrated pixel-for-
# pixel against a real `pdflatex` render of the supplied .tex (see the plan's
# Verification section). Two LaTeX box-placement quirks matter here:
#
# 1. A minipage placed with \put and no explicit valign argument is centred
#    on the \put point (its natural height is split evenly above/below), so
#    TITLE_Y/AUTHORS_Y below are the vertical CENTRE of each text block, not
#    its top or baseline.
# 2. \doublespacing's line pitch is fixed by \normalsize (12pt) *before*
#    \titlestyle/\authorstyle change the font size inside the minipage, so
#    both blocks share one absolute leading (~24pt) independent of their own
#    font size -- title (\LARGE = 20.74pt) and authors (\Large = 17.28pt)
#    would otherwise need different leadings, but empirically they don't.
#
# \makebox (the paper-number line) has no such quirk: its reference point is
# a normal baseline, confirmed by measurement.
TITLE_X = 0.06 * PAGE_WIDTH
TITLE_Y_CENTER = 0.45 * PAGE_HEIGHT
TITLE_WIDTH = 0.80 * PAGE_WIDTH
TITLE_FONT_SIZE = 20.74  # \LARGE at the 12pt document class.
TITLE_MIN_FONT_SIZE = 12

AUTHORS_X = 0.06 * PAGE_WIDTH
AUTHORS_Y_CENTER = 0.32 * PAGE_HEIGHT
AUTHORS_WIDTH = 0.60 * PAGE_WIDTH
AUTHORS_FONT_SIZE = 17.28  # \Large at the 12pt document class.
AUTHORS_MIN_FONT_SIZE = 12

BASE_LEADING = 24.0  # \doublespacing's line pitch at \normalsize, shared by both blocks.

NUMBER_X = 0.07 * PAGE_WIDTH
NUMBER_Y = 0.84 * PAGE_HEIGHT  # a plain baseline, per \makebox.
NUMBER_FONT_SIZE = 17.28  # \Large.


def format_authors(names):
    """Join author names the way the .tex's ``\\paperauthors`` sample does.

    ["A"] -> "A"; ["A", "B"] -> "A and B"; 3+ -> "A, B, and C".
    """
    names = [n for n in names if n]
    if not names:
        return ''
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f'{names[0]} and {names[1]}'
    return ', '.join(names[:-1]) + f', and {names[-1]}'


def _draw_centered_block(c, text, x, y_center, width, style_kwargs, base_size, min_size):
    """Draw a word-wrapped block whose vertical centre sits at ``y_center``
    (matching \\put + a valign-less minipage), shrinking the font -- and its
    proportionally-scaled leading -- until it fits on the page. A long title
    or a long author list would otherwise silently run off the artwork, which
    the fixed-position .tex has no protection against.
    """
    size = base_size
    while True:
        leading = BASE_LEADING * (size / base_size)
        style = ParagraphStyle(
            'cover', fontSize=size, leading=leading, alignment=TA_LEFT, **style_kwargs,
        )
        paragraph = Paragraph(text, style)
        _, height = paragraph.wrap(width, PAGE_HEIGHT)
        bottom = y_center - height / 2
        if PAGE_HEIGHT - height >= 0 and bottom >= 0 or size <= min_size:
            paragraph.drawOn(c, x, max(bottom, 0))
            return
        size -= 1


def render_cover_page(number, title, authors):
    """Render a single-page PDF: the vendored backdrop plus the paper's
    number, title, and authors overlaid in the .tex's positions/styles.

    ``number`` is the display label already formatted by the caller --
    a plain integer-like value ("5") for the regular series, or "J3" for a
    job-market paper's own series (see Publication.display_number) -- and is
    interpolated into "Discussion Paper No. {number}" as-is.

    Returns the page as bytes.
    """
    overlay_buffer = io.BytesIO()
    c = canvas.Canvas(overlay_buffer, pagesize=letter)

    _draw_centered_block(
        c, title.upper(), TITLE_X, TITLE_Y_CENTER, TITLE_WIDTH,
        {'fontName': FONT_BOLD, 'textColor': CARNELIAN},
        TITLE_FONT_SIZE, TITLE_MIN_FONT_SIZE,
    )
    _draw_centered_block(
        c, format_authors(authors), AUTHORS_X, AUTHORS_Y_CENTER, AUTHORS_WIDTH,
        {'fontName': FONT_BOLD, 'textColor': CARNELIAN},
        AUTHORS_FONT_SIZE, AUTHORS_MIN_FONT_SIZE,
    )

    c.setFont(FONT_REGULAR, NUMBER_FONT_SIZE)
    c.setFillColor(black)
    c.drawString(NUMBER_X, NUMBER_Y, f'Discussion Paper No. {number}')

    c.showPage()
    c.save()
    overlay_buffer.seek(0)

    backdrop_page = PdfReader(find_static('pdfs/cover_backdrop.pdf')).pages[0]
    overlay_page = PdfReader(overlay_buffer).pages[0]
    backdrop_page.merge_page(overlay_page)  # stack the text overlay onto the artwork

    writer = PdfWriter()
    writer.add_page(backdrop_page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def build_covered_pdf(original_bytes, number, title, authors):
    """Prepend a generated cover page to ``original_bytes`` (the author's
    uploaded PDF). Returns the combined PDF as bytes.

    Mirrors the .tex's \\hypersetup block by stamping the same fields into
    the combined PDF's document info dictionary.
    """
    cover_bytes = render_cover_page(number, title, authors)

    merger = PdfMerger()
    merger.append(io.BytesIO(cover_bytes))
    merger.append(io.BytesIO(original_bytes))
    merger.add_metadata({
        '/Title': title,
        '/Author': format_authors(authors),
        '/Subject': f'Discussion Paper No. {number}',
        '/Keywords': 'discussion paper',
    })

    output = io.BytesIO()
    merger.write(output)
    return output.getvalue()
