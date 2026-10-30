from django.conf import settings


def absolute_url(path):
    """Prefix a root-relative path with the configured public site URL."""
    return "{}{}".format(settings.SITE_URL.rstrip("/"), path)
