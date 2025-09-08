import json
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, ButtonHolder, HTML, Row, Column
from django import forms
from django.core.files.base import ContentFile
from django.urls import reverse_lazy
from django.conf import settings
from core.constants import COUNTRY_CHOICES
from .models import Publication
import os
from PyPDF2 import PdfMerger
from io import BytesIO

class PublicationForm(forms.ModelForm):
    class Meta:
        model = Publication
        fields = ['title', 'date', 'abstract', 'country_code', 'study_url', 'is_job_market', 'pdf']

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
    authors_input = forms.CharField(
        required=True,
        label='Authors',
        widget=forms.TextInput(attrs={'id': 'authors-input'}),
    )

    keywords_input = forms.CharField(
        required=True,
        label='Additional Keywords',
        widget=forms.TextInput(attrs={'id': 'keywords-input'}),
    )

    country_code = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        required=True,
        label='Country of Study',
    )

    study_url = forms.CharField(
        required=True,
        label='Link to Study',
    )

    is_job_market = forms.BooleanField(
        label='Is this a job market study?'
    )

    pdf = forms.FileField(
        label='Upload Paper'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            button_text = 'Update Paper'
            cancel_url = reverse_lazy('publication_detail', kwargs={'pk': self.instance.pk})
            
            if self.instance.keywords:

                initial_interests = self.instance.keywords
                self.fields["keywords_input"].widget.attrs['value'] = json.dumps(initial_interests)
                
            if self.instance.authors.exists():
                initial_authors = [
                    {"value": str(author)} for author in self.instance.authors.all()
                ]
                self.fields["authors_input"].widget.attrs['value'] = json.dumps(initial_authors)

        else:
            button_text = 'Submit Paper'
            cancel_url = reverse_lazy('publications')

        self.helper = FormHelper(self)
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'title',
            'authors_input',
            'date',
            'abstract',
            'country_code',
            'keywords_input',
            'study_url',
            'is_job_market',
            'pdf',
            ButtonHolder(
                Submit('submit', button_text, css_class='btn btn-primary me-3'),
                HTML(f'<a href="{cancel_url}" style="margin-bottom: 0" class="btn btn-secondary">Cancel</a>')
            )
        )
