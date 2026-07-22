"""Tests for the public contact form: rendering, storage, email, honeypot."""

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from core.models import ContactMessage


class ContactViewTests(TestCase):
    def setUp(self):
        self.url = reverse('contact')
        self.valid_payload = {
            'name': 'Ada Lovelace',
            'email': 'ada@example.com',
            'message': 'I found a broken link on the jobs page.',
            'website': '',  # honeypot left empty by real users
        }

    def test_get_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/contact.html')
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="message"')

    def test_post_valid_stores_and_emails(self):
        response = self.client.post(self.url, self.valid_payload)
        self.assertRedirects(response, f"{self.url}?sent=1")

        self.assertEqual(ContactMessage.objects.count(), 1)
        message = ContactMessage.objects.get()
        self.assertEqual(message.name, 'Ada Lovelace')
        self.assertEqual(message.email, 'ada@example.com')
        self.assertFalse(message.handled)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn('Ada Lovelace', sent.subject)
        self.assertEqual(sent.reply_to, ['ada@example.com'])
        self.assertIn('broken link', sent.body)

    def test_success_flag_shows_confirmation(self):
        response = self.client.get(self.url, {'sent': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'has been sent')

    def test_post_invalid_does_not_store(self):
        payload = dict(self.valid_payload, message='')
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_honeypot_silently_discards(self):
        payload = dict(self.valid_payload, website='http://spam.example')
        response = self.client.post(self.url, payload)
        # Bots get an indistinguishable success redirect...
        self.assertRedirects(response, f"{self.url}?sent=1")
        # ...but nothing is stored or emailed.
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_footer_contact_link_present_sitewide(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, f'href="{self.url}"')
