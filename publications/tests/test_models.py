from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import CustomUser
from publications.models import Author, Publication


def make_user(email="author@example.com", first_name="Jane", last_name="Doe"):
    return CustomUser.objects.create_user(
        email=email, password="pass12345",
        first_name=first_name, last_name=last_name, is_active=True,
    )


def make_admin():
    return CustomUser.objects.create_user(
        email="admin@example.com", password="pass12345",
        first_name="Ada", last_name="Min", role=CustomUser.Role.ADMIN,
        is_active=True,
    )


def make_publication(**overrides):
    fields = dict(
        title="A Study",
        abstract="Abstract text.",
        study_url="https://example.com/study",
    )
    fields.update(overrides)
    return Publication.objects.create(**fields)


class AuthorModelTests(TestCase):
    def test_str_uses_user_full_name_when_linked(self):
        user = make_user()
        author = Author.objects.create(user=user, name="ignored")
        self.assertEqual(str(author), "Jane Doe")

    def test_str_uses_name_when_anonymous(self):
        author = Author.objects.create(user=None, name="Anon Author")
        self.assertEqual(str(author), "Anon Author")

    def test_unique_together_user_and_name(self):
        user = make_user()
        Author.objects.create(user=user, name="Jane Doe")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Author.objects.create(user=user, name="Jane Doe")


class PublicationModelTests(TestCase):
    def test_str_returns_title(self):
        publication = make_publication(title="Labor Markets")
        self.assertEqual(str(publication), "Labor Markets")

    def test_approve_transitions_from_pending(self):
        admin = make_admin()
        publication = make_publication()
        publication.approve(admin)
        publication.refresh_from_db()
        self.assertEqual(publication.status, "approved")
        self.assertEqual(publication.reviewed_by, admin)
        self.assertIsNotNone(publication.reviewed_at)

    def test_approve_non_pending_raises(self):
        admin = make_admin()
        publication = make_publication(status="approved")
        with self.assertRaises(ValueError):
            publication.approve(admin)

    def test_reject_transitions_from_pending(self):
        admin = make_admin()
        publication = make_publication()
        publication.reject(admin)
        publication.refresh_from_db()
        self.assertEqual(publication.status, "rejected")
        self.assertEqual(publication.reviewed_by, admin)

    def test_reject_non_pending_raises(self):
        admin = make_admin()
        publication = make_publication(status="rejected")
        with self.assertRaises(ValueError):
            publication.reject(admin)
