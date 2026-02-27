from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, ButtonHolder, HTML
from django import forms
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
    
    class Meta:
        model = Event
        fields = ['title', 'description', 'date', 'end_date', 'location', 'category']

        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Event Description'}),
            'date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
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
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'title',
            'description',
            'date',
            'end_date',
            'location',
            'category',
            ButtonHolder(
                Submit('submit', 'Submit', css_class='btn btn-primary me-3'),
                HTML(f'<a href="{cancel_url}" style="margin-bottom: 0" class="btn btn-secondary">Cancel</a>')
            )
        )