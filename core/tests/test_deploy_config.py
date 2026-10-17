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

    def test_disk_is_not_set_in_the_config_file(self):
        # With flexible resources Upsun rejects a `disk:` key and aborts the whole
        # build ("disk configuration is not supported"; production deploy, 2026-10-16).
        # Disk is changed with `upsun resources:set --disk laborhub:<MB>` instead.
        self.assertNotIn("disk", self.app)

    def test_gunicorn_is_threaded_so_requests_do_not_queue_behind_one_another(self):
        # One sync worker made the affiliation list wait behind other visitors.
        command = self.app["web"]["commands"]["start"]
        self.assertIn("--worker-class gthread", command)
        threads = int(command.split("--threads")[1].split()[0])
        self.assertGreaterEqual(threads, 2)
