from django import forms
from .models import Publication
import datetime

class PublicationForm(forms.ModelForm):
    class Meta:
        model = Publication
        fields = [
            'title',
            'authors',
            'month',
            'year',
            'abstract',
            'country',
            'keywords',
            'study_url',
            'is_job_market',
            'pdf'
        ]
