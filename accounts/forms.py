import json

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.hashers import make_password

from core.constants import COUNTRY_CHOICES
from seminars.models import University

from .models import Profile, CustomUser, UserApplication, ResearchPaper

# Maximum research papers a researcher applicant may attach.
MAX_RESEARCH_PAPERS = 2


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        # The shared _form_field.html partial only emits the ``multiple``
        # attribute when it is present in widget.attrs, so set it here or the
        # browser file picker silently allows just one file.
        attrs = {"multiple": True, **(attrs or {})}
        super().__init__(attrs)

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

    department = forms.CharField(
        label='Department',
        widget=forms.TextInput()
    )

    position = forms.CharField(
        label='Position',
        widget=forms.TextInput(),
        required=False,
    )

    website = forms.URLField(
        label='Personal Website (optional)',
        widget=forms.URLInput(),
        required=False,
    )

    university = forms.ModelChoiceField(
        queryset=University.objects.none(),
        required=False,
        label='Affiliation',
        empty_label='Choose your institution',
        help_text="Pick a country first. Not listed? Type it in the box below.",
    )

    university_name = forms.CharField(
        required=False,
        label='Affiliation (if not listed above)',
        widget=forms.TextInput(),
    )

    class Meta:
        model = UserApplication
        fields = (
            "first_name",
            "last_name",
            "country_code",
            "university",
            "university_name",
            "department",
            "position",
            "motivation",
            "website",
            "resume",
            "email",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Same reasoning as UpdateProfileForm: accept any university on POST
        # while the rendered <select> is narrowed by country via JS.
        self.fields['university'].queryset = University.objects.order_by('name')

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
        label=f"Upload up to {MAX_RESEARCH_PAPERS} research papers (PDF only)",
        required=False)

    class Meta(BaseApplicationForm.Meta):
        fields = BaseApplicationForm.Meta.fields + ("research_papers",)

    def clean_research_papers(self):
        papers = [p for p in (self.cleaned_data.get("research_papers") or []) if p]
        if len(papers) > MAX_RESEARCH_PAPERS:
            raise forms.ValidationError(
                f"Please upload at most {MAX_RESEARCH_PAPERS} research papers."
            )
        return papers

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
        fields = ['avatar', 'position', 'department', 'university', 'university_name',
                  'country_code', 'website', 'biography']

    # These mirror Profile's blank=True fields. Declaring them required here
    # made a picture, a website and at least one research interest mandatory
    # before anyone could save any profile edit at all.
    avatar = forms.ImageField(
        label='Upload a profile picture',
        help_text='Please ensure that the image contains a clear subject.',
        widget=forms.FileInput,
        required=False,
    )

    biography = forms.CharField(
        label='Biography',
        widget=forms.Textarea(),
        required=False,
    )

    department = forms.CharField(
        label='Department',
        widget=forms.TextInput()
    )

    university = forms.ModelChoiceField(
        queryset=University.objects.none(),
        required=False,
        label='Affiliation',
        empty_label='Choose your institution',
        help_text="Pick a country first. Not listed? Type it in the box below.",
    )

    university_name = forms.CharField(
        required=False,
        label='Affiliation (if not listed above)',
        widget=forms.TextInput(),
    )

    position = forms.CharField(
        label='Position',
        widget=forms.TextInput()
    )

    country_code = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        required=True,
        label='Country',
    )

    website = forms.URLField(
        label='Personal Website',
        widget=forms.URLInput(),
        required=False,
    )

    research_interests_input = forms.CharField(
        label='Research Interests',
        widget=forms.TextInput(attrs={"id": "research-interests-input"}),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate the affiliation choices from the whole table so a POSTed
        # university validates, while the rendered <select> starts narrow and is
        # refilled by JS once a country is chosen.
        self.fields['university'].queryset = University.objects.order_by('name')

        if self.instance and self.instance.research_interests:
            initial_interests = self.instance.research_interests
            tagify_value = json.dumps([{"value": v} if isinstance(v, str) else v for v in initial_interests])
            self.fields["research_interests_input"].initial = tagify_value
            self.fields["research_interests_input"].widget.attrs['value'] = tagify_value


class EmailPreferencesForm(forms.ModelForm):
    digest_frequency = forms.ChoiceField(
        choices=Profile.DigestFrequency.choices,
        required=False,
        label='Email digest frequency',
        help_text='Get a summary email of newly added papers, events, jobs, and visits.',
        widget=forms.Select(),
    )

    class Meta:
        model = Profile
        fields = ['digest_frequency']

    def clean_digest_frequency(self):
        return self.cleaned_data.get('digest_frequency') or Profile.DigestFrequency.OFF
