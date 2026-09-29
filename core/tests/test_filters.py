"""Tests for core.filters.parse_pill_terms / map_country_terms_to_codes."""
from django.test import SimpleTestCase

from core.filters import map_country_terms_to_codes, parse_pill_terms


class ParsePillTermsTests(SimpleTestCase):
    def test_json_array_of_plain_strings(self):
        self.assertEqual(
            parse_pill_terms('["Wage Inequality", "Migration"]'),
            ["Wage Inequality", "Migration"],
        )

    def test_json_array_of_tagify_objects(self):
        self.assertEqual(
            parse_pill_terms('[{"value": "Wage Inequality"}, {"value": "Migration"}]'),
            ["Wage Inequality", "Migration"],
        )

    def test_comma_separated_fallback(self):
        self.assertEqual(
            parse_pill_terms("Wage Inequality,Migration"),
            ["Wage Inequality", "Migration"],
        )

    def test_a_comma_containing_term_stays_one_term_as_json(self):
        """Regression: "Structural models of health, retirement, and savings"
        (the one RECOMMENDED_KEYWORDS entry with commas) must survive as a
        single term when submitted as a JSON array -- the shape every pill
        input now writes (see static/js/tagify.js, users_list.html,
        publications.html)."""
        term = "Structural models of health, retirement, and savings"
        self.assertEqual(parse_pill_terms(f'["{term}"]'), [term])

    def test_a_comma_containing_term_still_splits_on_the_plain_comma_fallback(self):
        # The comma-list fallback is inherently ambiguous for a term that
        # itself contains commas -- this is exactly why every pill input now
        # submits JSON instead of relying on this path.
        term = "Structural models of health, retirement, and savings"
        self.assertNotEqual(parse_pill_terms(term), [term])

    def test_blank_returns_empty(self):
        self.assertEqual(parse_pill_terms(""), [])
        self.assertEqual(parse_pill_terms(None), [])

    def test_deduplicates_case_insensitively(self):
        self.assertEqual(
            parse_pill_terms('["Migration", "migration"]'), ["Migration"])


class MapCountryTermsToCodesTests(SimpleTestCase):
    def test_resolves_names_and_codes(self):
        self.assertEqual(
            sorted(map_country_terms_to_codes(["US", "Canada"])),
            sorted(["US", "CA"]),
        )

    def test_empty_terms_returns_empty(self):
        self.assertEqual(map_country_terms_to_codes([]), [])
