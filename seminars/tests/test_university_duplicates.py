from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser, Profile
from seminars.models import Seminar, University
from seminars.university_merge import merge_known_duplicates


def models_for_merge():
    from accounts.models import UserApplication
    return dict(University=University, Profile=Profile,
                UserApplication=UserApplication, Seminar=Seminar)


def uni(name, country, external_id, source="hipolabs", website=""):
    return University.objects.create(
        name=name, country_code=country, external_id=external_id, source=source, website=website)


class MergeDuplicatesTests(TestCase):
    def test_same_school_is_merged_and_references_follow(self):
        keep = uni("University of Bath", "GB", "bath.ac.uk")
        drop = uni("University of Bath", "GB", "bath.edu")
        user = CustomUser.objects.create_user(
            email="a@example.com", password="x", first_name="A", last_name="B", is_active=True)
        profile = Profile.objects.get(user=user) if Profile.objects.filter(user=user).exists() \
            else Profile.objects.create(user=user, position="p", department="d")
        profile.university = drop
        profile.alert_universities = [drop.pk, keep.pk, 999]
        profile.save()

        self.assertEqual(merge_known_duplicates(**models_for_merge()), 1)

        profile.refresh_from_db()
        self.assertEqual(profile.university, keep)
        self.assertEqual(profile.alert_universities, [keep.pk, 999])
        self.assertFalse(University.objects.filter(pk=drop.pk).exists())
        # Running again changes nothing.
        self.assertEqual(merge_known_duplicates(**models_for_merge()), 0)

    def test_different_schools_with_the_same_name_are_left_alone(self):
        uni("Glendale Community College", "US", "glendale.edu", website="http://www.glendale.edu/")
        uni("Glendale Community College", "US", "gccaz.edu", website="http://www.gccaz.edu/")
        merge_known_duplicates(**models_for_merge())
        self.assertEqual(University.objects.filter(name="Glendale Community College").count(), 2)

    def test_stray_write_in_is_merged_into_the_real_institution(self):
        real = uni("Yale University", "US", "yale.edu")
        uni("Yale", "US", "", source="write-in")
        merge_known_duplicates(**models_for_merge())
        self.assertEqual(list(University.objects.filter(country_code="US")), [real])

    def test_shenzhen_campus_is_renamed(self):
        uni("The Chinese University of Hong Kong", "HK", "cuhk.edu.hk")
        uni("The Chinese University of Hong Kong", "HK", "cuhk.edu.cn")
        merge_known_duplicates(**models_for_merge())
        self.assertTrue(University.objects.filter(
            name="The Chinese University of Hong Kong, Shenzhen").exists())


class UniversityEndpointTests(TestCase):
    def setUp(self):
        uni("Glendale Community College", "US", "glendale.edu", website="http://www.glendale.edu/")
        uni("Glendale Community College", "US", "gccaz.edu", website="http://www.gccaz.edu/")
        uni("Harvard University", "US", "harvard.edu", website="https://www.harvard.edu/")

    def test_repeated_names_show_their_domain(self):
        response = self.client.get(reverse("seminar-universities"), {"country": "US"})
        names = [u["name"] for u in response.json()["universities"]]
        self.assertIn("Glendale Community College (glendale.edu)", names)
        self.assertIn("Glendale Community College (gccaz.edu)", names)
        self.assertIn("Harvard University", names)

    def test_response_is_cacheable(self):
        response = self.client.get(reverse("seminar-universities"), {"country": "US"})
        self.assertIn("max-age=86400", response["Cache-Control"])
        self.assertIn("public", response["Cache-Control"])
