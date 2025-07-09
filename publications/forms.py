from django import forms
from .models import Publication
import datetime


class PublicationForm(forms.ModelForm):
    authors_input = forms.CharField(
        required=False,
        label='Authors',
        widget=forms.TextInput(attrs={'id': 'authors-input'}),
    )

    class Meta:
        model = Publication
        fields = [
            'title',
            'month',
            'year',
            'abstract',
            'country',
            'keywords',
            'study_url',
            'is_job_market',
            'pdf'
        ]
