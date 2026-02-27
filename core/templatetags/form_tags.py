from django import template
from datetime import date, datetime

register = template.Library()

def _normalize_date_value(raw_value):
    if raw_value in (None, ''):
        return ''
    if isinstance(raw_value, datetime):
        return raw_value.date().isoformat()
    if isinstance(raw_value, date):
        return raw_value.isoformat()

    value = str(raw_value).strip()
    if not value:
        return ''
    if 'T' in value:
        return value.split('T', 1)[0]
    if ' ' in value:
        return value.split(' ', 1)[0]
    return value

@register.inclusion_tag('partials/_form_field.html')
def render_field(field, label=None, placeholder=None, help_text=None, required=None):
    """
    Render a form field with consistent styling.
    
    Usage:
        {% render_field form.field_name label="Custom Label" placeholder="Enter value" %}
    """
    bound_field = field.field
    widget = bound_field.widget
    widget_name = widget.__class__.__name__
    raw_value = field.value()
    resolved_required = bound_field.required if required is None else required
    resolved_placeholder = placeholder
    if resolved_placeholder is None:
        resolved_placeholder = widget.attrs.get('placeholder', '')
    resolved_help_text = help_text
    if resolved_help_text is None:
        resolved_help_text = getattr(bound_field, 'help_text', '')

    return {
        'field': field,
        'label': label or field.label,
        'placeholder': resolved_placeholder,
        'help_text': resolved_help_text,
        'widget_name': widget_name,
        'date_value': _normalize_date_value(raw_value),
        'required': resolved_required,
    }

@register.inclusion_tag('partials/_select_field.html')
def render_select(field, label=None, empty_label=None, required=None):
    """
    Render a select field with custom option handling.
    
    Usage:
        {% render_select form.country_code label="Country" empty_label="Choose a country" %}
    """
    bound_field = field.field
    resolved_required = bound_field.required if required is None else required
    resolved_empty_label = empty_label
    if resolved_empty_label is None and hasattr(bound_field, 'empty_label'):
        resolved_empty_label = bound_field.empty_label or ''

    return {
        'field': field,
        'label': label or field.label,
        'empty_label': resolved_empty_label or '',
        'required': resolved_required,
    }