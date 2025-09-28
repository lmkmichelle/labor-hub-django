import json

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, ButtonHolder, HTML
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.hashers import make_password

from core.constants import COUNTRY_CHOICES
from .models import Profile, CustomUser, UserApplication, ResearchPaper


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result

class BaseApplicationForm(forms.ModelForm):
    research_papers = MultipleFileField(
        label="Upload up to 3 research papers (PDF only)",
        required=False )

    resume = forms.FileField(
        label="Upload your resume/CV (PDF only)",
        required=False
    )

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

    education = forms.CharField(
        label='Current Institution',
        widget=forms.TextInput()
    )

    position = forms.CharField(
        label='Current Affiliation',
        widget=forms.TextInput()
    )

    class Meta:
        model = UserApplication
        fields = (
            "email",
            "first_name",
            "last_name",
            "resume",
            "education",
            "position",
            "country_code",
            "motivation",
            "research_papers"
        )

    def save(self, commit=True):
        application = super().save(commit=False)
        application.password = make_password(self.cleaned_data["password1"])

        # Save the resume file if provided
        if self.cleaned_data.get('resume'):
            application.resume.save(self.cleaned_data["resume"])

        if commit:
            application.save()

            # Create research paper entries after the application is saved
            for paper in self.cleaned_data.get('research_papers', []):
                if paper:
                    ResearchPaper.objects.create(
                        application=application,
                        paper=paper
                    )

        return application

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        self.helper.layout = Layout(
            "first_name",
            "last_name",
            "education",
            "position",
            "country_code",
            "motivation",
            "resume",
            "research_papers",
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

class ResearcherApplicationForm(BaseApplicationForm):
    pass

class StudentApplicationForm(BaseApplicationForm):
    advisor = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(role=CustomUser.Role.RESEARCHER, is_active=True),
        label="Select an Advisor",
        help_text="Choose a researcher to act as your advisor",
    )

    class Meta(BaseApplicationForm.Meta):
        fields = BaseApplicationForm.Meta.fields + ("advisor",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        layout_fields = list(self.helper.layout.fields)
        button_holder = layout_fields.pop()

        layout_fields.append("advisor")
        layout_fields.append(button_holder)

        self.helper.layout.fields = layout_fields

    def clean_advisor(self):
        advisor = self.cleaned_data.get("advisor")
        if not advisor or advisor.role != CustomUser.Role.RESEARCHER:
            raise forms.ValidationError("Advisor must be a valid researcher.")
        return advisor

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
        fields = ['avatar', 'position', 'country_code', 'education', 'website', 'biography']

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

    position = forms.CharField(
        label='Current Affiliation',
        widget=forms.TextInput()
    )

    country_code = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        required=True,
        label='Country',
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
            'country_code',
            'website',
            'biography',
            'research_interests_input'
        )
