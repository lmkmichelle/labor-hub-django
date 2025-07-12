from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms
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
            'pdf'
        )
        self.helper.add_input(Submit('submit', 'Submit'))
