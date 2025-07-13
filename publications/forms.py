import json

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, ButtonHolder, HTML, Row, Column
from django import forms
from django.urls import reverse_lazy

from .models import Publication


class PublicationForm(forms.ModelForm):
    class Meta:
        model = Publication
        fields = ['title', 'month', 'year', 'abstract', 'country', 'study_url', 'is_job_market', 'pdf']

    authors_input = forms.CharField(
        required=True,
        label='Authors',
        widget=forms.TextInput(attrs={'id': 'authors-input'}),
    )

    keywords_input = forms.CharField(
        required=True,
        label='Keywords',
        widget=forms.TextInput(attrs={'id': 'keywords-input'}),
    )

    country = forms.CharField(
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

            if self.instance.authors.exists():
                initial_authors = [
                    {"value": str(author)} for author in self.instance.authors.all()
                ]
                self.fields["authors_input"].widget.attrs['value'] = json.dumps(initial_authors)

            if self.instance.keywords:
                initial_authors = [
                    {"value": kw} for kw in self.instance.keywords
                ]
                self.fields["keywords_input"].widget.attrs['value'] = json.dumps(initial_authors)

        else:
            button_text = 'Upload Paper'
            cancel_url = reverse_lazy('publications')

        self.helper = FormHelper(self)
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'title',
            'authors_input',
            'month',
            'year',
            'abstract',
            'country',
            'keywords_input',
            'study_url',
            'is_job_market',
            'pdf',
            ButtonHolder(
                Submit('submit', button_text, css_class='btn btn-primary me-3'),
                HTML(f'<a href="{cancel_url}" style="margin-bottom: 0" class="btn btn-secondary">Cancel</a>')
            )
        )
