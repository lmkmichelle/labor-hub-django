import json

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms
from .models import Profile, CustomUser


class UpdateUserForm(forms.ModelForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    class Meta:
        model = CustomUser
        fields = ['email']

class UpdateProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar', 'position', 'education', 'website', 'biography']

    avatar = forms.ImageField(
        label='Upload a profile picture',
        widget=forms.FileInput
    )

    biography = forms.CharField(
        label='Biography',
        widget=forms.Textarea()
    )

    research_interests_input = forms.CharField(
        label='Research Interests',
        widget=forms.TextInput(attrs={"id": "research-interests-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.research_interests:
            initial_keywords = [
                {"value": kw} for kw in self.instance.research_interests
            ]
            self.fields["research_interests_input"].widget.attrs['value'] = json.dumps(initial_keywords)

        self.helper = FormHelper(self)
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'avatar',
            'position',
            'education',
            'website',
            'biography',
            'research_interests_input'
        )

        self.helper.add_input(Submit('submit', 'Submit'))

