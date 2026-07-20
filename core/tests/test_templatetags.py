from datetime import date, datetime

from django import forms
from django.test import SimpleTestCase

from core.templatetags.form_tags import (
    _normalize_date_value,
    render_field,
    render_select,
)


class _SampleForm(forms.Form):
    name = forms.CharField(label="Name")
    country = forms.ChoiceField(choices=[("US", "United States")], label="Country")


class NormalizeDateValueTests(SimpleTestCase):
    def test_none_returns_empty(self):
        self.assertEqual(_normalize_date_value(None), "")

    def test_empty_string_returns_empty(self):
        self.assertEqual(_normalize_date_value(""), "")

    def test_datetime_returns_date_iso(self):
        self.assertEqual(
            _normalize_date_value(datetime(2025, 6, 1, 14, 30)), "2025-06-01")

    def test_date_returns_iso(self):
        self.assertEqual(_normalize_date_value(date(2025, 6, 1)), "2025-06-01")

    def test_iso_datetime_string_splits_on_t(self):
        self.assertEqual(_normalize_date_value("2025-06-01T14:30"), "2025-06-01")

    def test_space_separated_string_splits(self):
        self.assertEqual(_normalize_date_value("2025-06-01 14:30"), "2025-06-01")

    def test_plain_date_string_passthrough(self):
        self.assertEqual(_normalize_date_value("2025-06-01"), "2025-06-01")


class RenderFieldTests(SimpleTestCase):
    def test_render_field_context(self):
        form = _SampleForm()
        context = render_field(form["name"], placeholder="Enter name")
        self.assertEqual(context["label"], "Name")
        self.assertEqual(context["widget_name"], "TextInput")
        self.assertEqual(context["placeholder"], "Enter name")
        self.assertTrue(context["required"])
        self.assertEqual(context["date_value"], "")

    def test_render_field_label_override(self):
        form = _SampleForm()
        context = render_field(form["name"], label="Full Name")
        self.assertEqual(context["label"], "Full Name")


class RenderSelectTests(SimpleTestCase):
    def test_render_select_context(self):
        form = _SampleForm()
        context = render_select(form["country"], empty_label="Choose one")
        self.assertEqual(context["label"], "Country")
        self.assertEqual(context["empty_label"], "Choose one")
        self.assertTrue(context["required"])
