import json

from django import forms
from django.core.files.base import ContentFile

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

    is_revision = forms.BooleanField(
        required=False,
        label='Is this a revised version of a previous discussion paper?',
    )

    previous_number = forms.CharField(
        required=False,
        max_length=20,
        label='Number of the previous discussion paper',
        help_text='For example 323, or J3 for a job market paper. '
                  'If you are revising 323.1, enter 323.',
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self._original = None

        if self.instance and self.instance.pk:
            # Revisions are chosen when a paper is first submitted. Once a
            # paper is published its PDF is fixed for good: a new version is a
            # new submission, not an edit.
            del self.fields['is_revision']
            del self.fields['previous_number']
            if self.instance.status == 'approved':
                del self.fields['pdf']

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
                    {"value": str(author)} for author in self.instance.ordered_authors
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

    def clean_previous_number(self):
        return (self.cleaned_data.get('previous_number') or '').strip()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('is_revision'):
            raw = cleaned.get('previous_number', '')
            original = Publication.find_original(raw)
            if original is None:
                self.add_error(
                    'previous_number',
                    'We could not find a published discussion paper with that number.')
            elif not (self.user and original.is_authored_by(self.user)):
                self.add_error(
                    'previous_number',
                    'Only an author of the original paper can submit a revision.')
            else:
                self._original = original
                # A revision stays in its original's series (J3 -> J3.1).
                cleaned['is_job_market'] = original.is_job_market
                cleaned['jm_advisor'] = original.jm_advisor
                return cleaned
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

        if self._original is not None:
            publication.revision_of = self._original
            publication.jm_advisor_acknowledged = self._original.jm_advisor_acknowledged
            publication.jm_advisor_responded_at = self._original.jm_advisor_responded_at

        upload = self.cleaned_data.get('pdf')
        if upload:
            # Keep the author's file untouched on pdf_original -- the only
            # thing Publication.rebuild_covered_pdf() ever reads from -- and
            # mirror it onto pdf uncovered for now, so the author can still
            # download their own not-yet-approved paper. The branded cover
            # replaces it once the paper is approved (see approve()).
            content = ContentFile(upload.read())
            publication.pdf_original.save(upload.name, content, save=False)
            content.seek(0)
            publication.pdf.save(upload.name, ContentFile(content.read()), save=False)

        if commit:
            publication.save()
            self.save_m2m()

        return publication
