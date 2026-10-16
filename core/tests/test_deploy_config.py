from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase


class UpsunConfigTests(SimpleTestCase):
    def setUp(self):
        path = Path(settings.BASE_DIR) / ".upsun" / "config.yaml"
        self.app = yaml.safe_load(path.read_text())["applications"]["laborhub"]

    def test_gunicorn_timeout_leaves_room_for_a_large_pdf_cover_merge(self):
        # The default 30s killed an admin approval mid-merge (J1, 2026-10-16).
        command = self.app["web"]["commands"]["start"]
        self.assertIn("gunicorn nole.wsgi:application", command)
        timeout = int(command.split("--timeout")[1].split()[0])
        self.assertGreaterEqual(timeout, 120)
