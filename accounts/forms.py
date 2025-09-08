import json
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, ButtonHolder, HTML
from django import forms
from django.contrib.auth.forms import  AuthenticationForm
from django.contrib.auth.hashers import make_password

from .models import Profile, CustomUser, UserApplication

class UserApplicationForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
        help_text="Enter a secure password."
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput,
        help_text='Enter the same password as before, for verification.'
    )

    class Meta:
        model = UserApplication
        fields = (
            "email",
            "first_name",
            "last_name",
            "position",
            "education",
            "country_code",
            "motivation")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        self.helper.layout = Layout(
            "first_name",
            "last_name",
            "position",
            "education",
            "country_code",
            "motivation",
            "email",
            "password1",
            "password2",
            ButtonHolder(
                Submit('submit', "Apply", css_class='btn btn-primary me-3'),
                HTML(f'<a href="/" style="margin-bottom: 0" class="btn btn-secondary">Cancel</a>')
            )
        )

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if password1 != password2:
            raise forms.ValidationError("Passwords don't match")

        return password2

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")

        if UserApplication.objects.filter(email=email, status='pending').exists():
            raise forms.ValidationError("An application with this email is already pending review.")

        return email

    def save(self, commit=True):
        application = super().save(commit=False)
        application.password = make_password(self.cleaned_data["password1"])

        if commit:
            application.save()

        return application

class CustomLoginForm(AuthenticationForm):
    class Meta:
        model = CustomUser
        fields = ("username", "password")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'username',
            'password',
            ButtonHolder(
                Submit('submit', "Log in", css_class='btn btn-primary me-3'),
                HTML(f'<a href="/" style="margin-bottom: 0" class="btn btn-secondary">Cancel</a>')
            )
        )


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
        help_text='Please ensure that the image contains a clear subject.',
        widget=forms.FileInput
    )

    biography = forms.CharField(
        label='Biography',
        widget=forms.Textarea()
    )

    education = forms.CharField(
        label='Current Institution',
        widget=forms.TextInput()
    )

    website = forms.URLField(
        label='Personal Website',
        widget=forms.URLInput()
    )

    research_interests_input = forms.CharField(
        label='Research Interests',
        widget=forms.TextInput(attrs={"id": "research-interests-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.research_interests:
            initial_interests = self.instance.research_interests
            self.fields["research_interests_input"].widget.attrs['value'] = json.dumps(initial_interests)

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
