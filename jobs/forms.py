from django import forms

from core.constants import COUNTRY_CHOICES

from .models import Job


class JobForm(forms.ModelForm):
    country_code = forms.ChoiceField(
        choices=[('', 'Choose a country')] + list(COUNTRY_CHOICES),
        required=True,
        label='Country',
    )

    class Meta:
        model = Job
        fields = [
            'title',
            'country_code',
            'description',
            'url',
            'deadline',
            'is_for_graduate_students',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'deadline': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'title': 'Job Title',
            'description': 'Job Description',
            'url': 'Application URL',
            'deadline': 'Application Deadline',
            'is_for_graduate_students': 'For Graduate Students',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['title'].required = True
        self.fields['country_code'].required = True
        self.fields['description'].required = True
        self.fields['url'].required = True
        self.fields['deadline'].required = True

        existing_countries = self.instance.countries if self.instance and self.instance.pk else []
        if existing_countries:
            self.fields['country_code'].initial = existing_countries[0]

    def clean_country_code(self):
        return (self.cleaned_data.get('country_code') or '').strip().upper()

    def save(self, commit=True):
        instance = super().save(commit=False)
        country_code = (self.cleaned_data.get('country_code') or '').strip().upper()
        instance.countries = [country_code] if country_code else []
        if commit:
            instance.save()
            self.save_m2m()
        return instance

