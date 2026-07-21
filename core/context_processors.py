from core.constants import RECOMMENDED_KEYWORDS


def recommended_keywords(request):
    """Expose the recommended keyword vocabulary to every template.

    Used by base.html (JSON payload for Tagify-powered forms) and by the
    Discussion Papers keyword filter dropdown.
    """
    return {"recommended_keywords": RECOMMENDED_KEYWORDS}
