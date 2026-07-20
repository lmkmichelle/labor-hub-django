from django.test import TestCase

from accounts.models import CustomUser, Profile


class ProfileSignalTests(TestCase):
    def test_profile_created_on_user_creation(self):
        user = CustomUser.objects.create_user(
            email="new@example.com", password="pass12345",
            first_name="New", last_name="User",
        )
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)
        profile = user.profile
        self.assertEqual(profile.position, "")
        self.assertEqual(profile.education, "")
        self.assertEqual(profile.research_interests, [])

    def test_profile_not_duplicated_on_resave(self):
        user = CustomUser.objects.create_user(
            email="resave@example.com", password="pass12345",
            first_name="Re", last_name="Save",
        )
        user.first_name = "Changed"
        user.save()
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)
