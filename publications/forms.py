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
        fields = ['title', 'abstract', 'country_code', 'jm_advisor', 'pdf']

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

    # Replaces the old "job market paper" / "revised version" checkboxes: one
    # choice, shown as three cards, each revealing only its own fields.
    PAPER_TYPES = [
        ('discussion', 'Discussion paper'),
        ('job_market', 'Job market paper'),
        ('revision', 'Revision of a previous paper'),
    ]
    paper_type = forms.ChoiceField(
        choices=PAPER_TYPES,
        widget=forms.RadioSelect,
        initial='discussion',
        label='Type of paper',
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

    # Tagify (single pill) writes JSON here: [{"value": "323 - Title", "id": 42}].
    # Only the id is used, and it is re-checked against revisable_by() in clean().
    revision_of_input = forms.CharField(
        required=False,
        label='Paper you are revising',
        help_text='Only papers you submitted or are an author of. '
                  'To revise 323.1, pick 323.',
        widget=forms.TextInput(attrs={'id': 'revision-of-input'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self._original = None
        self._is_job_market = False
        self.is_student = bool(user and user.role == CustomUser.Role.STUDENT)
        self.revisable = list(Publication.revisable_by(user)) if user else []
        if self.is_student:
            # Students only post job market papers, so only those can be revised.
            self.revisable = [p for p in self.revisable if p.is_job_market]

        if self.instance and self.instance.pk:
            # A revision is chosen when a paper is first submitted. Once a
            # paper is published its PDF is fixed for good: a new version is a
            # new submission, not an edit.
            del self.fields['revision_of_input']
            if self.instance.revision_of_id:
                # A revision stays in its original's series; nothing to choose.
                del self.fields['paper_type']
            else:
                # Editing never changes a paper into a revision; if no type is
                # posted the paper simply keeps the one it has.
                self.fields['paper_type'].choices = self.PAPER_TYPES[:2]
                self.fields['paper_type'].required = False
                self.fields['paper_type'].initial = (
                    'job_market' if self.instance.is_job_market else 'discussion')
            if self.instance.status == 'approved':
                del self.fields['pdf']

        if self.is_student and 'paper_type' in self.fields:
            # No discussion-paper card for students: job market or its revision.
            self.fields['paper_type'].choices = [
                c for c in self.fields['paper_type'].choices if c[0] != 'discussion']
            self.fields['paper_type'].initial = 'job_market'

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

    @property
    def revision_whitelist(self):
        """The papers the picker offers, as Tagify whitelist entries."""
        return [
            {'value': f'[{paper.display_number}] {paper.title}', 'id': paper.pk}
            for paper in self.revisable
        ]

    def _chosen_paper_id(self):
        """The pk Tagify submitted, or None. Accepts its JSON and a bare id."""
        raw = (self.cleaned_data.get('revision_of_input') or '').strip()
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except ValueError:
            data = raw
        if isinstance(data, list):
            data = data[0] if data else None
        if isinstance(data, dict):
            data = data.get('id')
        try:
            return int(data)
        except (TypeError, ValueError):
            return None

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and self.instance.revision_of_id:
            # Editing a revision: its series and advisor were fixed at submission.
            self._is_job_market = self.instance.is_job_market
            cleaned['jm_advisor'] = self.instance.jm_advisor
            return cleaned

        paper_type = cleaned.get('paper_type')
        if not paper_type and self.instance.pk:
            paper_type = 'job_market' if self.instance.is_job_market else 'discussion'
        self._is_job_market = paper_type == 'job_market'

        if paper_type == 'revision':
            chosen = self._chosen_paper_id()
            if chosen is None:
                self.add_error('revision_of_input', 'Select the paper you are revising.')
            else:
                # Checked server-side: Tagify's whitelist is only a convenience,
                # a hand-made POST could name anyone's paper.
                original = next((p for p in self.revisable if p.pk == chosen), None)
                if original is None:
                    self.add_error(
                        'revision_of_input',
                        'You can only revise papers you submitted or authored.')
                else:
                    self._original = original
                    # A revision stays in its original's series (J3 -> J3.1).
                    self._is_job_market = original.is_job_market
                    cleaned['jm_advisor'] = original.jm_advisor
                    return cleaned
            return cleaned

        if paper_type == 'job_market' and not cleaned.get('jm_advisor'):
            self.add_error(
                'jm_advisor',
                'Select your advisor for a job market paper.',
            )
        if paper_type != 'job_market':
            # An advisor picked under another type is ignored.
            cleaned['jm_advisor'] = None
        return cleaned

    def save(self, commit=True):
        publication = super().save(commit=False)
        publication.is_job_market = self._is_job_market

        if self._original is not None:
            publication.revision_of = self._original
            if not self.is_student:
                # A fellow's revision inherits the original's advisor response; a
                # student's goes back to the advisor for approval.
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
