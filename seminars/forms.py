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
            'university',
            'university_name',
            'visit_type',
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
            'university': 'University',
            'university_name': "Institution not listed? Enter it here",
            'visit_type': 'Visit Type',
            'visit_start': 'Visit Start Date',
            'visit_end': 'Visit End Date (Optional)',
            'description': 'Details (Optional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['visit_start'].required = True
        self.fields['country_code'].required = True

        self.fields['visit_type'].required = True
        self.fields['visit_type'].choices = (
            [('', 'Choose a visit type')] + list(Seminar.VisitType.choices)
        )

        self.fields['description'].required = False
        self.fields['university'].queryset = University.objects.order_by('name')
        # Either the list pick or a written-in name satisfies the form;
        # clean() enforces that one of them is present.
        self.fields['university'].required = False
        self.fields['university'].help_text = (
            "Pick a country first, then choose from the list. "
            "Not there? Write it in below."
        )
        self.fields['university_name'].required = False
        self.fields['university_name'].help_text = (
            "Only needed if your institution isn't in the list above."
        )
        self.fields['visit_end'].required = False

        # Seed dropdown from existing JSON list when editing.
        existing_countries = self.instance.countries if self.instance and self.instance.pk else []
        if existing_countries:
            self.fields['country_code'].initial = existing_countries[0]

    def clean_country_code(self):
        return (self.cleaned_data.get('country_code') or '').strip().upper()

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['university_name'] = (cleaned_data.get('university_name') or '').strip()
        if cleaned_data.get('university'):
            # The list wins; don't keep a stale write-in alongside it.
            cleaned_data['university_name'] = ''
        elif not cleaned_data['university_name']:
            self.add_error('university', 'Choose a university from the list or write in your institution.')
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
