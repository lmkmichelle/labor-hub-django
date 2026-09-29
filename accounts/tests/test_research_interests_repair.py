"""Tests for the 0022 data migration that repairs research interests split
by the Tagify comma-delimiter bug (see static/js/tagify.js's delimiters:
null fix and the migration's own docstring)."""
import importlib

from django.test import SimpleTestCase, TestCase

from accounts.models import CustomUser, Profile

_migration = importlib.import_module(
    "accounts.migrations.0022_merge_comma_split_research_interests"
)
merge_split_fragments = _migration.merge_split_fragments
merge_research_interests = _migration.merge_research_interests

KEYWORD = "Structural models of health, retirement, and savings"


class MergeSplitFragmentsTests(SimpleTestCase):
    def test_merges_the_three_split_fragments(self):
        merged, changed = merge_split_fragments(
            ["Migration", "Structural models of health", "retirement",
             "and savings", "Job search"]
        )
        self.assertTrue(changed)
        self.assertEqual(merged, ["Migration", KEYWORD, "Job search"])

    def test_already_correct_list_is_untouched(self):
        merged, changed = merge_split_fragments(["Migration", KEYWORD])
        self.assertFalse(changed)
        self.assertEqual(merged, ["Migration", KEYWORD])

    def test_unrelated_list_is_untouched(self):
        merged, changed = merge_split_fragments(["Migration", "Job search"])
        self.assertFalse(changed)
        self.assertEqual(merged, ["Migration", "Job search"])

    def test_empty_list(self):
        merged, changed = merge_split_fragments([])
        self.assertFalse(changed)
        self.assertEqual(merged, [])


class MergeResearchInterestsMigrationTests(TestCase):
    def test_repairs_saved_profiles_in_place(self):
        user = CustomUser.objects.create_user(
            email="split@example.com", password="pass12345",
            first_name="Split", last_name="Fragments", is_active=True,
        )
        user.profile.research_interests = [
            "Structural models of health", "retirement", "and savings",
        ]
        user.profile.save(update_fields=["research_interests"])

        from django.apps import apps
        merge_research_interests(apps, None)

        user.profile.refresh_from_db()
        self.assertEqual(user.profile.research_interests, [KEYWORD])

    def test_leaves_an_unaffected_profile_alone(self):
        user = CustomUser.objects.create_user(
            email="fine@example.com", password="pass12345",
            first_name="Fine", last_name="Already", is_active=True,
        )
        user.profile.research_interests = ["Migration"]
        user.profile.save(update_fields=["research_interests"])

        from django.apps import apps
        merge_research_interests(apps, None)

        user.profile.refresh_from_db()
        self.assertEqual(user.profile.research_interests, ["Migration"])
