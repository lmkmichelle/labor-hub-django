from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from seminars.models import Seminar


class SeminarModelTests(TestCase):
    def test_str_includes_title_host_and_date(self):
        host = CustomUser.objects.create_user(
            email="host@example.com", password="pass12345",
            first_name="Host", last_name="User", is_active=True,
        )
        date = timezone.now() + timedelta(days=1)
        seminar = Seminar.objects.create(
            title="Sabbatical Visit", host=host, date=date,
            location="Ithaca", description="Details.",
        )
        expected = f"Sabbatical Visit by {host} on {date.strftime('%Y-%m-%d')}"
        self.assertEqual(str(seminar), expected)
