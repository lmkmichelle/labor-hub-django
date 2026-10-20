from django.test import TestCase


class RejectionEmailWordingTests(TestCase):
    def test_rejection_message_states_the_reasons_and_invites_reapplying(self):
        from django.core import mail
        from accounts.emails import send_application_rejected_email
        from accounts.models import UserApplication

        application = UserApplication.objects.create(
            email="r@example.com", first_name="Rae", last_name="Ject", password="x")
        send_application_rejected_email(application)
        message = mail.outbox[-1]
        for text in (message.body, message.alternatives[0][0]):
            self.assertIn("not able to accept your application", text)
            self.assertIn("poor fit with labor economics", text)
            self.assertIn("insufficient evidence of recent publication record in Labor Economics", text)
            self.assertIn("apply again in the future", text)
