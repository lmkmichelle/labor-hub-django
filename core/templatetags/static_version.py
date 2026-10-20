import os

from django import template
from django.contrib.staticfiles.finders import find
from django.templatetags.static import static

register = template.Library()


def _version(path):
    """Changes whenever the file may have: the deploy's tree id on Upsun, else the
    file's mtime (local development)."""
    tree = os.environ.get("PLATFORM_TREE_ID")
    if tree:
        return tree[:12]
    found = find(path)
    try:
        return str(int(os.path.getmtime(found))) if found else ""
    except OSError:
        return ""


@register.simple_tag
def static_v(path):
    """``{% static %}`` plus ``?v=...``. Our JS is served unhashed with a one-hour
    cache lifetime, so without this a browser can run last deploy's script against
    this deploy's HTML (the map panel never opened for people who had visited)."""
    url = static(path)
    version = _version(path)
    return f"{url}?v={version}" if version else url
