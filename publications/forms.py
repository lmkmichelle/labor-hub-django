from django import forms
from .models import Publication
import datetime

class PublicationForm(forms.ModelForm):
    month = forms.ChoiceField(choices=[('January', 'January'),])
