from django.contrib import admin
from django import forms
from core.constants import COUNTRY_CHOICES

from seminars.models import Seminar, University


class SeminarAdminForm(forms.ModelForm):
    countries = forms.MultipleChoiceField(
        choices=COUNTRY_CHOICES,
        required=False,
        widget=forms.SelectMultiple,
        help_text='Hold Ctrl/Cmd to select multiple countries.',
    )

    class Meta:
        model = Seminar
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['countries'].initial = self.instance.countries if self.instance and self.instance.pk else []

    def clean_countries(self):
        return list(self.cleaned_data.get('countries', []))


# Register your models here.

class SeminarAdmin(admin.ModelAdmin):
    form = SeminarAdminForm
    list_display = ['title', 'visitor_name', 'get_university_name', 'visit_start', 'visit_end', 'posted_by']
    search_fields = ['title', 'visitor_name', 'visitor_email', 'university__name', 'university_name', 'description']
    list_filter = ['visit_start', 'countries']

    fieldsets = (
        ('Seminar Information', {
            'fields': (
                'title',
                'posted_by',
                'visitor_name',
                'visitor_email',
                'visitor_affiliation',
                'university',
                'university_name',
                'visit_start',
                'visit_end',
                'countries',
                'description',
            )
        }),
    )

    def get_university_name(self, obj):
        return obj.get_university_display()
    get_university_name.short_description = 'University'


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ['name', 'country_code', 'website', 'source']
    search_fields = ['name', 'country_code', 'source', 'external_id']

admin.site.register(Seminar, SeminarAdmin)

