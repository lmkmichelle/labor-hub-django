import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]


def settings_value(expr, **env):
    """Evaluate ``expr`` against nole.settings in a clean process."""
    base = {k: v for k, v in os.environ.items()
            if not k.startswith(("PLATFORM_", "CM_", "ALLOW_"))}
    base.update(env, DJANGO_SETTINGS_MODULE="nole.settings", DJANGO_SECRET_KEY="x")
    out = subprocess.run(
        [sys.executable, "-c", f"from nole import settings as s; print({expr})"],
        cwd=ROOT, env=base, capture_output=True, text=True, check=True)
    return out.stdout.strip()


CM = {"CM_API_KEY": "k", "CM_CLIENT_ID": "c"}


class CampaignMonitorOnlyOnProductionTests(SimpleTestCase):
    def test_production_uses_campaign_monitor(self):
        self.assertEqual(settings_value("s.CAMPAIGN_DELIVERY",
                                        PLATFORM_ENVIRONMENT_TYPE="production", **CM), "cm")

    def test_local_without_the_platform_variable_is_unchanged(self):
        self.assertEqual(settings_value("s.CAMPAIGN_DELIVERY", **CM), "cm")

    def test_staging_never_uses_the_inherited_live_key(self):
        for kind in ("staging", "development"):
            self.assertEqual(settings_value("s.CAMPAIGN_DELIVERY",
                                            PLATFORM_ENVIRONMENT_TYPE=kind, **CM), "smtp")

    def test_it_can_be_allowed_on_purpose(self):
        self.assertEqual(settings_value(
            "s.CAMPAIGN_DELIVERY", PLATFORM_ENVIRONMENT_TYPE="staging",
            CM_ALLOW_NON_PRODUCTION="1", **CM), "cm")

    def test_environment_file_silences_mail_off_production(self):
        script = (
            'export PLATFORM_ENVIRONMENT_TYPE="$T" PLATFORM_ROUTES="$(echo {} | base64)" '
            'EMAIL_HOST_PASSWORD=tok; . ./.environment 2>/dev/null; echo "$EMAIL_BACKEND"')
        def backend(kind):
            return subprocess.run(["bash", "-c", script], cwd=ROOT, capture_output=True,
                                  text=True, env={**os.environ, "T": kind}).stdout.strip()
        self.assertTrue(backend("staging").endswith("console.EmailBackend"))
        self.assertTrue(backend("production").endswith("CampaignMonitorEmailBackend"))
