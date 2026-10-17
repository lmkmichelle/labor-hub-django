from django import template
from django.core.paginator import Paginator

register = template.Library()


@register.simple_tag
def elided_pages(page_obj):
    """Page numbers to render: first, last and the neighbours of the current page,
    with ``Paginator.ELLIPSIS`` for each gap (``1 … 8 9 10 … 17``), so a long list
    never produces a row of 17 buttons."""
    return list(page_obj.paginator.get_elided_page_range(
        page_obj.number, on_each_side=1, on_ends=1))


@register.simple_tag
def is_ellipsis(value):
    return value == Paginator.ELLIPSIS
