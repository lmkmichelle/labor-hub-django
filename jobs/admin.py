from django import forms
from django.contrib import admin

from core.admin import ApprovableAdmin
from core.constants import COUNTRY_CHOICES

from .models import Job


class JobAdminForm(forms.ModelForm):
    countries = forms.MultipleChoiceField(
        choices=COUNTRY_CHOICES,
        required=False,
        widget=forms.SelectMultiple,
        help_text='Hold Ctrl/Cmd to select multiple countries.',
    )

    class Meta:
        model = Job
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['countries'].initial = self.instance.countries if self.instance and self.instance.pk else []

    def clean_countries(self):
        return list(self.cleaned_data.get('countries', []))


@admin.register(Job)
class JobAdmin(ApprovableAdmin):
    form = JobAdminForm
    list_display = ('title', 'employer', 'display_categories', 'uploader', 'deadline')
    search_fields = ('title', 'employer', 'description', 'uploader__first_name', 'uploader__last_name', 'uploader__email')
    ordering = ('deadline',)

    fieldsets = (
        ('Job Information', {
            'fields': ('title', 'employer', 'pay', 'uploader', 'description',
                       'countries', 'categories', 'url', 'deadline')
        }),
        ('Review', {
            'fields': ('review_actions', 'status', 'admin_notes', 'reviewed_at', 'reviewed_by')
        }),
    )

    @admin.display(description='Titles')
    def display_categories(self, obj):
        return ', '.join(obj.category_labels()) or '—'
