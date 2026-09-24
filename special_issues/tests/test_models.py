from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from special_issues.models import SpecialIssue


def make_fellow(email="fellow@example.com", first="Fay", last="Fellow"):
    return CustomUser.objects.create_user(
        email=email, password="x", first_name=first, last_name=last,
        role=CustomUser.Role.RESEARCHER, is_active=True,
    )


def make_issue(posted_by=None, editors=None, deadline_offset=30, status="approved", **kw):
    return SpecialIssue.objects.create(
        journal=kw.pop("journal", "Journal of Tests"),
        title=kw.pop("title", "A Special Issue"),
        description="About things. https://example.org/cfp",
        submission_deadline=timezone.localdate() + timedelta(days=deadline_offset),
        posted_by=posted_by,
        editors=editors or [],
        status=status,
        **kw,
    )


class SpecialIssueEditorTests(TestCase):
    def test_save_inserts_poster_as_first_editor(self):
        fellow = make_fellow()
        issue = make_issue(
            posted_by=fellow,
            editors=[{"name": "Guest Editor", "user_id": None}],
        )
        issue.refresh_from_db()
        self.assertEqual(
            issue.editor_entries(),
            [
                {"name": "Fay Fellow", "user_id": fellow.id},
                {"name": "Guest Editor", "user_id": None},
            ],
        )

    def test_save_never_duplicates_poster(self):
        fellow = make_fellow()
        issue = make_issue(posted_by=fellow)
        issue.save()
        issue.save()
        issue.refresh_from_db()
        self.assertEqual(len(issue.editor_entries()), 1)

    def test_poster_moves_to_front_if_listed_later(self):
        fellow = make_fellow()
        issue = make_issue(
            posted_by=fellow,
            editors=[
                {"name": "Guest", "user_id": None},
                {"name": "Fay Fellow", "user_id": fellow.id},
            ],
        )
        self.assertEqual(issue.editor_entries()[0]["user_id"], fellow.id)
        self.assertEqual(len(issue.editor_entries()), 2)

    def test_is_open_reflects_deadline(self):
        self.assertTrue(make_issue(deadline_offset=1).is_open)
        self.assertFalse(make_issue(deadline_offset=-1).is_open)

    def test_only_approved_are_public(self):
        make_issue(status="approved")
        make_issue(status="pending")
        self.assertEqual(SpecialIssue.objects.approved().count(), 1)
