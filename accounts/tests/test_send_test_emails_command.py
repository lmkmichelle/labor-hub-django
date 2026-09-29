"""Tests for the send_test_emails management command's --preview mode
(rendering HTML locally, with the inline logo inlined further as a data URI,
without sending anything)."""
import os
import tempfile

from django.core import mail
from django.core.management import call_command
from django.test import TestCase


class SendTestEmailsPreviewTests(TestCase):
    def test_preview_writes_one_html_file_per_key_plus_an_index(self):
        with tempfile.TemporaryDirectory() as out_dir:
            call_command(
                "send_test_emails", "--preview", "--out", out_dir,
                "--only", "approved,contact,contact_confirmation",
            )
            files = sorted(os.listdir(out_dir))
            self.assertEqual(
                files,
                ["approved.html", "contact.html", "contact_confirmation.html", "index.html"],
            )

            with open(os.path.join(out_dir, "approved.html")) as f:
                approved_html = f.read()
            self.assertNotIn("cid:", approved_html)
            self.assertIn("data:image/png;base64,", approved_html)

            with open(os.path.join(out_dir, "index.html")) as f:
                index_html = f.read()
            self.assertIn("approved.html", index_html)
            self.assertIn("contact_confirmation.html", index_html)

    def test_preview_never_actually_sends_mail(self):
        with tempfile.TemporaryDirectory() as out_dir:
            call_command(
                "send_test_emails", "--preview", "--out", out_dir,
                "--only", "approved",
            )
            self.assertEqual(len(mail.outbox), 0)

    def test_preview_defaults_to_a_placeholder_recipient(self):
        with tempfile.TemporaryDirectory() as out_dir:
            call_command(
                "send_test_emails", "--preview", "--out", out_dir,
                "--only", "approved",
            )
            with open(os.path.join(out_dir, "approved.html")) as f:
                html = f.read()
            self.assertIn("preview@example.com", html)
