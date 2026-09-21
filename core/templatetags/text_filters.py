import re

from django import template
from django.utils.text import normalize_newlines

register = template.Library()

# A blank line is a real paragraph break; anything else is a "soft" wrap.
_PARAGRAPH_BREAK = re.compile(r'\n[ \t]*\n+')
_SOFT_BREAK = re.compile(r'[ \t]*\n[ \t]*')


@register.filter
def soften_linebreaks(value):
    """Collapse hard-wrapped newlines into spaces before `linebreaks` runs.

    Abstracts and descriptions are often pasted from a PDF or word processor
    that hard-wraps every line at a fixed width, usually with Windows-style
    "\\r\\n" line endings. Django's `linebreaks` filter turns each of those
    newlines into a `<br>`, so the text wraps at the *source document's* line
    width instead of the reader's actual screen width -- on a wide screen
    this leaves a large blank column next to a narrow ragged edge of text.
    A genuine blank line (an intentional paragraph break) is left alone.

    `normalize_newlines` runs first so a stray "\\r" (left over from a
    "\\r\\n" pair once its "\\n" is collapsed below) can't survive to be
    re-expanded into a break by `linebreaks`, which normalizes newlines
    internally too.

    Apply immediately before `linebreaks`/`urlize`, e.g.
    ``{{ text|soften_linebreaks|linebreaks }}``.
    """
    if not value:
        return value
    value = normalize_newlines(value)
    paragraphs = _PARAGRAPH_BREAK.split(value.strip())
    return '\n\n'.join(_SOFT_BREAK.sub(' ', p).strip() for p in paragraphs)
