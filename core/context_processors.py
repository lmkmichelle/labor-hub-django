from core.constants import RECOMMENDED_KEYWORDS


def recommended_keywords(request):
    """Expose the recommended keyword vocabulary to every template.

    Used by base.html (JSON payload for Tagify-powered forms) and by the
    Discussion Papers keyword filter dropdown.
    """
    return {"recommended_keywords": RECOMMENDED_KEYWORDS}


def pending_advisee_count(request):
    """Number of pending student applications naming this user as advisor.

    Short-circuits to 0 for anonymous users and non-researchers so it costs no
    query on the public site; base.html uses it to show an "Advisees" link with
    a count badge only for researchers who have advisees to review.
    """
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated and user.is_researcher()):
        return {"pending_advisee_count": 0}

    from accounts.models import CustomUser, UserApplication

    return {
        "pending_advisee_count": UserApplication.objects.filter(
            advisor=user,
            role=CustomUser.Role.STUDENT,
            status=UserApplication.Status.PENDING,
        ).count()
    }
