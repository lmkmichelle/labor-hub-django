from unittest import mock

from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser, UserApplication
from publications.models import Author

PASSWORD = "correct-horse-1"


class DeleteAccountTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="leaving@example.com", password=PASSWORD,
            first_name="Lee", last_name="Ving", role=CustomUser.Role.RESEARCHER,
            is_active=True)
        self.client.force_login(self.user)

    def test_settings_links_to_the_delete_page(self):
        self.assertContains(self.client.get(reverse("settings")), reverse("delete_account"))

    def test_wrong_password_deletes_nothing(self):
        response = self.client.post(reverse("delete_account"), {"password": "nope"})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(CustomUser.objects.filter(pk=self.user.pk).exists())

    def test_deleting_removes_user_applications_and_keeps_the_byline(self):
        author = Author.objects.create(user=self.user)
        UserApplication.objects.create(
            email="leaving@example.com", first_name="Lee", last_name="Ving",
            role=CustomUser.Role.RESEARCHER, password="x")
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("delete_account"), {"password": PASSWORD})
        self.assertContains(response, "has been deleted")
        self.assertFalse(CustomUser.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(UserApplication.objects.filter(email="leaving@example.com").exists())
        author.refresh_from_db()
        self.assertIsNone(author.user)
        self.assertEqual(author.name, "Lee Ving")
        self.assertEqual(str(author), "Lee Ving")

    def test_uploaded_files_leave_storage(self):
        application = UserApplication.objects.create(
            email="leaving@example.com", first_name="Lee", last_name="Ving",
            role=CustomUser.Role.RESEARCHER, password="x")
        application.resume.save("cv.pdf", ContentFile(b"%PDF-1.4"), save=True)
        name, storage = application.resume.name, application.resume.storage
        self.assertTrue(storage.exists(name))
        with self.captureOnCommitCallbacks(execute=True):
            self.user.delete()
        self.assertFalse(storage.exists(name))

    def test_an_admin_delete_runs_the_same_cleanup(self):
        with mock.patch("accounts.cm_sync.remove_subscriber") as remove, \
                self.captureOnCommitCallbacks(execute=True):
            self.user.delete()
        remove.assert_called_once_with("leaving@example.com")

    def test_a_campaign_monitor_failure_does_not_block_the_delete(self):
        with mock.patch("accounts.cm_sync.is_configured", return_value=True), \
                mock.patch("accounts.cm_sync.cm_lists.provisioned", return_value=True), \
                mock.patch("accounts.cm_sync.cm_lists.list_id", return_value="l1"), \
                mock.patch("accounts.cm_sync.CampaignMonitorClient") as client, \
                self.captureOnCommitCallbacks(execute=True):
            client.return_value.delete_subscriber.side_effect = RuntimeError("down")
            self.user.delete()
        self.assertFalse(CustomUser.objects.filter(pk=self.user.pk).exists())
