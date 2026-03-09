from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, ButtonHolder, HTML
from datetime import time as dtime, datetime
from django import forms
from django.utils import timezone
from django.urls import reverse_lazy

from .models import Event

class EventForm(forms.ModelForm):
    title = forms.CharField(
        label="Event Title",
        widget=forms.TextInput,
        required=True,
    )

    description = forms.CharField(
        label="Event Description",
        widget=forms.Textarea,
        required=False
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
        label="Application Deadline Date",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        required=False,
    )

    deadline_time = forms.TimeField(
        label="Application Deadline Time (optional, defaults to 11:59 PM)",
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        required=False,
        initial='23:59',
    )

    class Meta:
        model = Event
        fields = ['title', 'description', 'date', 'end_date', 'deadline', 'location', 'category']

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
        cancel_url = reverse_lazy('events-list')

        self.fields['end_date'].required = False
        self.fields['deadline'].required = False

        # Pre-populate split fields when editing an existing event
        if self.instance and self.instance.pk and self.instance.deadline:
            self.fields['deadline_date'].initial = self.instance.deadline.date()
            self.fields['deadline_time'].initial = self.instance.deadline.strftime('%H:%M')

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'title',
            'description',
            'date',
            'end_date',
            'deadline_date',
            'deadline_time',
            'location',
            'category',
            ButtonHolder(
                Submit('submit', 'Submit', css_class='btn btn-primary me-3'),
                HTML(f'<a href="{cancel_url}" style="margin-bottom: 0" class="btn btn-secondary">Cancel</a>')
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        deadline_date = cleaned_data.get('deadline_date')
        deadline_time = cleaned_data.get('deadline_time')

        if deadline_date:
            t = deadline_time if deadline_time else dtime(23, 59)
            naive_dt = datetime.combine(deadline_date, t)
            cleaned_data['deadline'] = timezone.make_aware(naive_dt)
        else:
            cleaned_data['deadline'] = None

        return cleaned_data