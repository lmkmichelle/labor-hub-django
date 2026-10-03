import json
import logging

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.contrib.auth.hashers import make_password
from django.core.mail import EmailMultiAlternatives
from django.template import loader

from core.constants import COUNTRY_CHOICES, OTHER_NETWORK_CHOICES, RECOMMENDED_KEYWORDS
from core.email import attach_logo, cm_headers, default_reply_to
from core.filters import map_country_terms_to_codes, parse_pill_terms, serialize_pill_terms
from seminars.models import University

from .models import Profile, CustomUser, UserApplication, ResearchPaper

logger = logging.getLogger(__name__)

# The two named research-paper upload fields on ResearcherApplicationForm,
# in the order they should be saved as ResearchPaper rows.
RESEARCH_PAPER_FIELDS = ("research_paper_1", "research_paper_2")


class BaseApplicationForm(forms.ModelForm):
    cv_url = forms.URLField(
        label="Link to your CV (optional)",
        help_text="If you keep an up-to-date CV online, link it here instead of uploading one.",
        widget=forms.URLInput(),
        required=False,
    )

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

    other_networks = forms.MultipleChoiceField(
        choices=OTHER_NETWORK_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'w-4 h-4 text-brand bg-gray-100 border-gray-300 '
                     'rounded focus:ring-brand focus:ring-2',
        }),
        label='Are you a member of any of the following other networks?',
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
            "cv_url",
            "resume",
            "email",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Same reasoning as UpdateProfileForm: accept any university on POST
        # while the rendered <select> is narrowed by country via JS.
        self.fields['university'].queryset = University.objects.order_by('name')

        # One URL field per network, shown by JS only when its box is ticked.
        for code, _label in OTHER_NETWORK_CHOICES:
            self.fields[f'network_url_{code.lower()}'] = forms.URLField(
                required=False, label=f'{code} profile URL',
            )

    def clean(self):
        cleaned = super().clean()
        selected = cleaned.get('other_networks') or []
        cleaned['other_networks_payload'] = [
            {
                'network': code,
                'url': cleaned.get(f'network_url_{code.lower()}', '') or '',
            }
            for code, _label in OTHER_NETWORK_CHOICES
            if code in selected
        ]
        return cleaned

    def save(self, commit=True):
        application = super().save(commit=False)
        application.password = make_password(self.cleaned_data["password1"])
        application.other_networks = self.cleaned_data.get(
            'other_networks_payload', [])

        if commit:
            application.save()

            # Create a research paper entry for each filled upload slot.
            for field_name in RESEARCH_PAPER_FIELDS:
                paper = self.cleaned_data.get(field_name)
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
    # Two explicit slots, not one multi-select input -- discoverable without
    # needing to know a shift/cmd-click trick to attach a second paper.
    research_paper_1 = forms.FileField(
        label="Research paper 1 (PDF)",
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf"}),
    )
    research_paper_2 = forms.FileField(
        label="Research paper 2 (PDF)",
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf"}),
    )

    class Meta(BaseApplicationForm.Meta):
        fields = BaseApplicationForm.Meta.fields + RESEARCH_PAPER_FIELDS

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


class LaborHubPasswordResetForm(PasswordResetForm):
    """Adds the CM grouping/reply-to headers and the inline logo to the
    password-reset email -- Django's own ``send_mail`` builds the message
    itself, so there's no other hook to reuse ``core.email.attach_logo`` from.
    Otherwise identical to ``PasswordResetForm.send_mail``."""

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        subject = loader.render_to_string(subject_template_name, context)
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        message = EmailMultiAlternatives(
            subject, body, from_email, [to_email],
            reply_to=default_reply_to(),
            headers=cm_headers(),
        )
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            message.attach_alternative(html_email, "text/html")
        attach_logo(message)
        try:
            message.send()
        except Exception:
            logger.exception(
                "Failed to send password reset email to %s", context["user"].pk
            )


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
        help_text='Ensure the image contains a clear subject.',
        widget=forms.FileInput,
        required=False,
    )

    # Written by static/js/avatar-editor.js from Cropper.js's getData() when the
    # user frames/rotates their picture in the editor. Left blank (and safely
    # ignored -- see clean_avatar_crop) with JS disabled or when no file was
    # re-picked, so the no-JS path just gets the old centred crop.
    avatar_crop = forms.CharField(widget=forms.HiddenInput, required=False)

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

    def clean_avatar_crop(self):
        """Parse the JSON box avatar-editor.js writes into a plain dict, or None if it's
        blank/malformed -- either way this must never block saving the rest of the form,
        since it just means accounts.utils.process_avatar falls back to a centred crop."""
        raw = self.cleaned_data.get('avatar_crop')
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        try:
            crop = {
                'x': float(data.get('x', 0)),
                'y': float(data.get('y', 0)),
                'width': float(data.get('width', 0)),
                'height': float(data.get('height', 0)),
                'rotate': int(float(data.get('rotate', 0))) // 90 * 90,
            }
        except (TypeError, ValueError):
            return None
        if crop['width'] <= 0 or crop['height'] <= 0:
            return None
        return crop


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


class AlertPreferencesForm(forms.ModelForm):
    """Settings-page form for the weekly topic/country alert email.

    Both fields are Tagify pill inputs submitting the same JSON-array-or-
    comma-string shape the list-page filters use, so they're parsed the same
    way (core.filters.parse_pill_terms). Countries accept a name or an ISO
    code (map_country_terms_to_codes); topics are limited to
    RECOMMENDED_KEYWORDS.
    """
    alert_topics = forms.CharField(
        required=False,
        label='Email me about new papers on these topics',
        widget=forms.TextInput(attrs={"id": "alert-topics-input"}),
    )
    alert_countries = forms.CharField(
        required=False,
        label='Email me about new visits to these countries',
        widget=forms.TextInput(attrs={"id": "alert-countries-input"}),
    )

    class Meta:
        model = Profile
        fields = ['alert_topics', 'alert_countries']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Overwrite the instance-derived initial values (Python lists, which
        # would render as "['DE']") with the JSON the pill inputs read back.
        # Setting field.initial isn't enough: a ModelForm's self.initial,
        # built from the instance, takes precedence over it.
        if self.instance and self.instance.pk:
            self.initial['alert_topics'] = serialize_pill_terms(
                self.instance.alert_topics)
            self.initial['alert_countries'] = serialize_pill_terms(
                self.instance.alert_countries)

    def clean_alert_topics(self):
        """Keep only recognised topics, stored in their canonical spelling, so
        alert matching against Publication.topic stays exact."""
        canonical = {kw.lower(): kw for kw in RECOMMENDED_KEYWORDS}
        raw = self.cleaned_data.get('alert_topics', '')
        topics = []
        for term in parse_pill_terms(raw):
            keyword = canonical.get(term.strip().lower())
            if keyword and keyword not in topics:
                topics.append(keyword)
        return topics

    def clean_alert_countries(self):
        raw = self.cleaned_data.get('alert_countries', '')
        return map_country_terms_to_codes(parse_pill_terms(raw))
