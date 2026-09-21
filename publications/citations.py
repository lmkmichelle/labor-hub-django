"""Builds the downloadable BibTeX citation for a discussion paper.

Formatted to match NBER's own ``@techreport`` export (the sample the feedback
request supplied), minus the ``doi`` field -- Labor Hub papers don't have one.
"""
from django.utils import timezone

_ESCAPES = {
    '&': r'\&',
    '%': r'\%',
    '$': r'\$',
    '#': r'\#',
    '_': r'\_',
    '{': r'\{',
    '}': r'\}',
}


def _escape(value):
    """Escape LaTeX specials and a literal ``"`` for a double-quote-delimited
    BibTeX field. Without this, a title or abstract containing ``&`` or a
    quote mark produces a ``.bib`` file that fails to parse."""
    out = []
    for ch in value:
        if ch in _ESCAPES:
            out.append(_ESCAPES[ch])
        elif ch == '"':
            out.append("''")
        else:
            out.append(ch)
    return ''.join(out)


def format_author_name(author):
    """"Last, First" -- BibTeX's canonical author order.

    A linked user's first/last name fields are used directly; a free-text
    name is split on whitespace and the last token treated as the surname
    (a single-token name is returned unchanged).
    """
    if author.user:
        return f"{author.user.last_name}, {author.user.first_name}"
    parts = author.name.split()
    if len(parts) < 2:
        return author.name
    return f"{parts[-1]}, {' '.join(parts[:-1])}"


def cite_key(publication):
    """A short, stable BibTeX key: "LaborHubJ3" for a job-market paper's own
    series, "LaborHubDP5" for the regular series -- mirroring how
    Publication.display_number keeps the two apart."""
    if publication.job_market_paper_number is not None:
        return f"LaborHubJ{publication.job_market_paper_number}"
    return f"LaborHubDP{publication.discussion_paper_number}"


def build_bibtex(publication, url):
    """The full ``.bib`` file contents, as a string. Callers must only call
    this once ``publication.display_number`` is set."""
    authors = " and ".join(
        format_author_name(author) for author in publication.authors.all()
    )
    applied = timezone.localtime(publication.applied_at)

    lines = [
        "% WARNING: This file may contain UTF-8 (unicode) characters.",
        "% While non-8-bit characters are officially unsupported in BibTeX, you",
        "% can use them with the biber backend of biblatex",
        "%    usepackage[backend=biber]{biblatex}",
        "",
        f"@techreport{{{cite_key(publication)},",
        f' title = "{_escape(publication.title)}",',
        f' author = "{_escape(authors)}",',
        ' institution = "Cornell University ILR School",',
        ' type = "Discussion Paper",',
        ' series = "Labor Hub Discussion Paper Series",',
        f' number = "{publication.display_number}",',
        f' year = "{applied:%Y}",',
        f' month = "{applied:%B}",',
        f' URL = "{url}",',
        f' abstract = {{{publication.abstract}}},',
        "}",
    ]
    return "\n".join(lines) + "\n"
