import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from special_issues.models import SpecialIssue

from .test_models import make_fellow, make_issue


def make_student(email="student@example.com"):
    return CustomUser.objects.create_user(
        email=email, password="x", first_name="Stu", last_name="Dent",
        role=CustomUser.Role.STUDENT, is_active=True,
    )


class SpecialIssueCreateTests(TestCase):
    url = property(lambda self: reverse("special-issue-create"))

    def payload(self, **overrides):
        data = {
            "journal": "Journal of Tests",
            "title": "Labor and AI",
            "description": "Call for papers at https://example.org/cfp",
            "call_url": "https://example.org/cfp",
            "submission_deadline": "2099-01-31",
            "editors_input": "",
        }
        data.update(overrides)
        return data

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_student_gets_403(self):
        self.client.force_login(make_student())
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 403)
        self.assertEqual(SpecialIssue.objects.count(), 0)

    def test_fellow_can_load_form(self):
        self.client.force_login(make_fellow())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fay Fellow (you)")

    def test_fellow_posts_pending_issue_with_self_as_first_editor(self):
        fellow = make_fellow()
        other = make_fellow(email="other@example.com", first="Olive", last="Other")
        self.client.force_login(fellow)
        editors = json.dumps([
            {"value": "Olive Other", "id": str(other.id)},
            {"value": "Fay Fellow", "id": str(fellow.id)},
            {"value": "Jo Outsider"},
        ])
        response = self.client.post(self.url, self.payload(editors_input=editors))
        self.assertEqual(response.status_code, 302)
        issue = SpecialIssue.objects.get()
        self.assertEqual(issue.status, "pending")
        self.assertEqual(issue.posted_by, fellow)
        self.assertEqual(
            [(e["name"], e["user_id"]) for e in issue.editor_entries()],
            [("Fay Fellow", fellow.id), ("Olive Other", other.id), ("Jo Outsider", None)],
        )

    def test_missing_required_field_is_rejected(self):
        self.client.force_login(make_fellow())
        response = self.client.post(self.url, self.payload(journal=""))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SpecialIssue.objects.count(), 0)


class SpecialIssueListAndDetailTests(TestCase):
    def test_list_shows_only_approved_open_issues(self):
        make_issue(title="Open One")
        make_issue(title="Pending One", status="pending")
        make_issue(title="Closed One", deadline_offset=-3)
        response = self.client.get(reverse("special-issues-list"))
        self.assertContains(response, "Open One")
        self.assertNotContains(response, "Pending One")
        self.assertNotContains(response, "Closed One")

    def test_show_closed_lists_past_deadlines(self):
        make_issue(title="Closed One", deadline_offset=-3)
        response = self.client.get(reverse("special-issues-list"), {"show_closed": "1"})
        self.assertContains(response, "Closed One")

    def test_search_matches_editor_names(self):
        make_issue(title="Alpha", editors=[{"name": "Zed Zimmer", "user_id": None}])
        make_issue(title="Beta")
        response = self.client.get(reverse("special-issues-list"), {"q": "Zimmer"})
        self.assertContains(response, "Alpha")
        self.assertNotContains(response, "Beta")

    def test_pending_detail_is_hidden_except_from_poster(self):
        fellow = make_fellow()
        issue = make_issue(posted_by=fellow, status="pending")
        url = reverse("special-issue-detail", args=[issue.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(fellow)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_detail_links_member_editors_to_profiles(self):
        fellow = make_fellow()
        issue = make_issue(posted_by=fellow)
        response = self.client.get(reverse("special-issue-detail", args=[issue.pk]))
        self.assertContains(response, f'href="{reverse("profile", args=[fellow.pk])}"')
        self.assertContains(response, "Fay Fellow")

    def test_only_owner_can_delete(self):
        fellow = make_fellow()
        issue = make_issue(posted_by=fellow)
        url = reverse("special-issue-delete", args=[issue.pk])
        self.client.force_login(make_fellow(email="x@example.com"))
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(fellow)
        self.client.post(url)
        self.assertEqual(SpecialIssue.objects.count(), 0)
