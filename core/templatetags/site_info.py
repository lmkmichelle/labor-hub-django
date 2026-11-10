from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def postal_address():
    """The organisation's postal address (settings.LABOR_HUB_POSTAL_ADDRESS).

    A tag rather than a context processor so it also works in emails, which are
    rendered with explicit contexts and no request.
    """
    return settings.LABOR_HUB_POSTAL_ADDRESS
