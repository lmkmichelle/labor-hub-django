from django.contrib import admin
from django import forms
from core.admin import ApprovableAdmin
from core.constants import COUNTRY_CHOICES

from seminars.models import Seminar


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

class SeminarAdmin(ApprovableAdmin):
    form = SeminarAdminForm
    list_display = ['visitor_name', 'get_university_name', 'visit_start', 'visit_end', 'posted_by']
    search_fields = [ 'visitor_name', 'visitor_email', 'university__name', 'university_name', 'description']
    list_filter = ['visit_start', 'countries']

    fieldsets = (
        ('Visit Information', {
            'fields': (
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
        ('Review', {
            'fields': ('review_actions', 'status', 'admin_notes', 'reviewed_at', 'reviewed_by')
        }),
    )

    def get_university_name(self, obj):
        return obj.get_university_display()
    get_university_name.short_description = 'University'


# University is reference data (populated by import_universities and picked
# from a dropdown on the public forms) rather than something admins moderate
# or edit by hand, so it is deliberately not registered here.
admin.site.register(Seminar, SeminarAdmin)

