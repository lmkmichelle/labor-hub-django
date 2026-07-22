from django import forms

from .models import ContactMessage


class ContactForm(forms.ModelForm):
    """Public contact form: name, email, message.

    Includes a hidden ``website`` honeypot field. It stays empty for real
    visitors (it is not shown to them), so a non-empty value flags an
    automated submission, which the view silently discards.
    """

    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}),
    )

    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'message']
        labels = {
            'name': 'Name',
            'email': 'Email',
            'message': 'Message',
        }
        widgets = {
            'message': forms.Textarea(attrs={
                'placeholder': 'How can we help?',
            }),
        }

    def is_spam(self):
        """True when the honeypot was filled in (i.e. a likely bot)."""
        return bool(self.cleaned_data.get('website'))
