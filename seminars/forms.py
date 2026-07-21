from django import forms

from core.constants import COUNTRY_CHOICES
from seminars.models import Seminar, University


class SeminarForm(forms.ModelForm):
    country_code = forms.ChoiceField(
        choices=[('', 'Choose a country')] + list(COUNTRY_CHOICES),
        required=True,
        label='Country',
    )

    class Meta:
        model = Seminar
        fields = [
            'country_code',
            'visitor_name',
            'visitor_email',
            'visitor_affiliation',
            'university',
            'university_name',
            'visit_start',
            'visit_end',
            'description',
        ]
        widgets = {
            'visit_start': forms.DateInput(attrs={'type': 'date'}),
            'visit_end': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 5}),
        }
        labels = {
            'visitor_name': 'Your Name',
            'visitor_email': 'Your Email',
            'visitor_affiliation': 'Affiliation (Optional)',
            'university': 'University (Choose from list)',
            'university_name': 'University Name (if not listed)',
            'visit_start': 'Visit Start Date',
            'visit_end': 'Visit End Date (Optional)',
            'description': 'Seminar Details',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['visitor_name'].required = True
        self.fields['visitor_email'].required = True
        self.fields['visit_start'].required = True
        self.fields['description'].required = True
        self.fields['country_code'].required = True

        self.fields['university'].queryset = University.objects.order_by('name')
        self.fields['university'].required = False
        self.fields['university_name'].required = False
        self.fields['visit_end'].required = False

        # Seed dropdown from existing JSON list when editing.
        existing_countries = self.instance.countries if self.instance and self.instance.pk else []
        if existing_countries:
            self.fields['country_code'].initial = existing_countries[0]

    def clean_country_code(self):
        return (self.cleaned_data.get('country_code') or '').strip().upper()

    def clean(self):
        cleaned_data = super().clean()
        country_code = cleaned_data.get('country_code')
        cleaned_data['countries'] = [country_code] if country_code else []
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        country_code = (self.cleaned_data.get('country_code') or '').strip().upper()
        instance.countries = [country_code] if country_code else []
        if commit:
            instance.save()
            self.save_m2m()
        return instance
