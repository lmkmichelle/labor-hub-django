from datetime import time as dtime, datetime

# Deadlines with no time component are treated as end-of-day.
DEADLINE_DEFAULT_TIME = dtime(23, 59)
from django import forms
from django.utils import timezone

from .models import Event


class EventForm(forms.ModelForm):
    title = forms.CharField(
        label="Event Title",
        widget=forms.TextInput,
        required=True,
    )

    description = forms.CharField(
        label="Description & Application Instructions",
        widget=forms.Textarea,
        required=False,
        help_text="Include how and where to apply or register, if relevant.",
    )

    application_url = forms.URLField(
        label="Application Link (Optional)",
        widget=forms.URLInput,
        required=False,
    )
    
    date = forms.DateField(
        label="Event Date",
        widget=forms.DateInput,
        required=True
    )
    
    end_date = forms.DateField(
        label="(Optional) End Date",
            widget=forms.DateInput,
        required=False
    )
    
    location = forms.CharField(
        label="Location of Event",
        widget=forms.TextInput,
        max_length=255,
        required=True
    )

    deadline_date = forms.DateField(
        label="Application Deadline (Optional)",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        required=False,
    )

    class Meta:
        model = Event
        fields = ['title', 'description', 'date', 'end_date', 'deadline',
                  'application_url', 'location', 'category']

        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Event Description'}),
            'date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'deadline': forms.HiddenInput(),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Location'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'date': 'Start Date & Time',
            'end_date': 'End Date & Time (Optional)',
            'category': 'Event Category',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['end_date'].required = False
        self.fields['deadline'].required = False

        # Members cannot submit a Live Podcast; admins add those directly.
        self.fields['category'].choices = Event.PUBLIC_CATEGORY_CHOICES

        # Pre-populate the split field when editing an existing event
        if self.instance and self.instance.pk and self.instance.deadline:
            local_deadline = timezone.localtime(self.instance.deadline)
            self.fields['deadline_date'].initial = local_deadline.date()

    def clean(self):
        cleaned_data = super().clean()
        deadline_date = cleaned_data.get('deadline_date')

        if deadline_date:
            naive_dt = datetime.combine(deadline_date, DEADLINE_DEFAULT_TIME)
            cleaned_data['deadline'] = timezone.make_aware(naive_dt)
        else:
            cleaned_data['deadline'] = None

        return cleaned_data