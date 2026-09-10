import json
import os
from io import BytesIO

from django import forms
from django.conf import settings
from django.core.files.base import ContentFile
from PyPDF2 import PdfMerger

from accounts.models import CustomUser
from core.constants import PAPER_COUNTRY_CHOICES, RECOMMENDED_KEYWORDS
from .models import Publication
from .utils import handle_keywords


class PublicationForm(forms.ModelForm):
    class Meta:
        model = Publication
        fields = ['title', 'abstract', 'country_code', 'is_job_market',
                  'jm_advisor', 'pdf']

    authors_input = forms.CharField(
        required=True,
        label='Authors',
        widget=forms.TextInput(attrs={'id': 'authors-input'}),
    )

    topics_input = forms.CharField(
        required=True,
        label='Research Topic(s)',
        widget=forms.TextInput(attrs={'id': 'topics-input'}),
    )

    country_code = forms.ChoiceField(
        choices=PAPER_COUNTRY_CHOICES,
        required=True,
        label='Country of Study',
    )

    is_job_market = forms.BooleanField(
        required=False,
        label='Is this a job market paper?',
    )

    jm_advisor = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),
        required=False,
        label='Advisor on Job Market Paper?',
        help_text='The researcher supervising this job market paper.',
    )

    pdf = forms.FileField(
        required=False,
        label='Upload Paper',
        widget=forms.ClearableFileInput(attrs={'accept': 'application/pdf'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['jm_advisor'].queryset = CustomUser.objects.filter(
            role=CustomUser.Role.RESEARCHER, is_active=True,
        ).order_by('first_name', 'last_name')

        if self.instance and self.instance.pk:
            if self.instance.topic:
                self.fields["topics_input"].widget.attrs['value'] = json.dumps(
                    [{"value": t} for t in self.instance.topic]
                )
            if self.instance.authors.exists():
                initial_authors = [
                    {"value": str(author)} for author in self.instance.authors.all()
                ]
                self.fields["authors_input"].widget.attrs['value'] = json.dumps(initial_authors)

    def clean_topics_input(self):
        """Enforce the closed research-topic vocabulary server-side.

        Tagify's ``enforceWhitelist`` is client-only; a hand-crafted POST could
        still carry anything. Values are matched case-insensitively and returned
        in their canonical RECOMMENDED_KEYWORDS spelling.
        """
        values = handle_keywords(self.cleaned_data.get('topics_input', ''))
        allowed = {k.lower(): k for k in RECOMMENDED_KEYWORDS}
        cleaned, unknown = [], []
        for value in values:
            match = allowed.get(value.strip().lower())
            if match:
                if match not in cleaned:
                    cleaned.append(match)
            else:
                unknown.append(value)
        if unknown:
            raise forms.ValidationError(
                "Not a recognised research topic: " + ", ".join(unknown)
            )
        if not cleaned:
            raise forms.ValidationError("Select at least one research topic.")
        return cleaned

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('is_job_market') and not cleaned.get('jm_advisor'):
            self.add_error(
                'jm_advisor',
                'Select your advisor for a job market paper.',
            )
        if not cleaned.get('is_job_market'):
            # An advisor picked without ticking the box is ignored.
            cleaned['jm_advisor'] = None
        return cleaned

    def save(self, commit=True):
        publication = super().save(commit=False)

        if self.cleaned_data.get('pdf'):
            cover_path = os.path.join(settings.STATIC_ROOT, 'pdfs', 'cover.pdf')

            merger = PdfMerger()
            merger.append(cover_path)
            merger.append(self.cleaned_data.get('pdf'))

            output = BytesIO()
            merger.write(output)
            output.seek(0)

            publication.pdf.save(
                self.cleaned_data.get('pdf').name,
                ContentFile(output.getvalue()),
                save=False
            )

        if commit:
            publication.save()
            self.save_m2m()

        return publication
