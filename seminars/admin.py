from django.contrib import admin
from django import forms
from core.constants import COUNTRY_CHOICES

from seminars.models import Seminar, SeminarInterest


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
    list_display = ['title', 'host', 'date', 'description']
    search_fields = ['title', 'host__first_name', 'host__last_name', 'description']

    fieldsets = (
        ('Seminar Information', {
            'fields': ('title', 'host', 'date', 'countries', 'description')
        }),
    )

admin.site.register(Seminar, SeminarAdmin)


class SeminarInterestAdmin(admin.ModelAdmin):
    list_display = ['seminar', 'user', 'guest_name', 'guest_email', 'created_at']
    search_fields = ['seminar__title', 'user__email', 'guest_name', 'guest_email']


admin.site.register(SeminarInterest, SeminarInterestAdmin)
