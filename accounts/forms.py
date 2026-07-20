import json

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

    class Meta:
        model = UserApplication
        fields = (
            "email",
            "first_name",
            "last_name",
            "resume",
            "education",
            "country_code",
            "motivation"
        )

    def save(self, commit=True):
        application = super().save(commit=False)
        application.password = make_password(self.cleaned_data["password1"])

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
    research_papers = MultipleFileField(
        label="Upload up to 3 research papers (PDF only)",
        required=False)

    class Meta(BaseApplicationForm.Meta):
        fields = BaseApplicationForm.Meta.fields + ("research_papers",)

class AdvisorChoiceField(forms.ModelChoiceField):
    """Renders advisor options as "Full Name - Position" (presentation only)."""

    def label_from_instance(self, obj):
        profile = getattr(obj, "profile", None)
        position = getattr(profile, "position", None) or "Researcher"
        return f"{obj.get_full_name()} - {position}"


class StudentApplicationForm(BaseApplicationForm):
    advisor = AdvisorChoiceField(
        queryset=CustomUser.objects.filter(role=CustomUser.Role.RESEARCHER, is_active=True),
        label="Select an Advisor",
        help_text="Choose a researcher to act as your advisor",
    )

    class Meta(BaseApplicationForm.Meta):
        fields = BaseApplicationForm.Meta.fields + ("advisor",)

    def save(self, commit=True):
        application = super().save(commit=False)
        application.role = CustomUser.Role.STUDENT  # Set role to student
        if commit:
            application.save()

        return application

    def clean_advisor(self):
        advisor = self.cleaned_data.get("advisor")
        if not advisor or advisor.role != CustomUser.Role.RESEARCHER:
            raise forms.ValidationError("Advisor must be a valid researcher.")
        return advisor

class CustomLoginForm(AuthenticationForm):
    
    username = forms.CharField(
        label="Email",
        widget=forms.EmailInput,
    )
    
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput
    )
    class Meta:
        model = CustomUser
        fields = ("username", "password")


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
            tagify_value = json.dumps([{"value": v} if isinstance(v, str) else v for v in initial_interests])
            self.fields["research_interests_input"].initial = tagify_value
            self.fields["research_interests_input"].widget.attrs['value'] = tagify_value
