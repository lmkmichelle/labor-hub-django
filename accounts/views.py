import json
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Q, When
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, UpdateView, ListView

from core.constants import COUNTRY_CHOICES, RECOMMENDED_KEYWORDS
from core.models import ApprovalStatus
from events.models import Event
from jobs.models import Job
from seminars.models import Seminar, University, university_label
from publications.models import Publication
from accounts.utils import process_avatar
from publications.utils import handle_keywords
from .alerts import read_unsubscribe_token as read_alert_unsubscribe_token
from .unsubscribe import read_newsletter_unsubscribe_token
from .emails import send_advisor_review_email, send_application_submitted_email
from .forms import UpdateProfileForm, UpdateUserForm, CustomLoginForm, BaseApplicationForm, ResearcherApplicationForm, \
    StudentApplicationForm, EmailPreferencesForm, AlertPreferencesForm
from .models import CustomUser, Profile, ResearchPaper, UserApplication


class BaseApplicationView(CreateView):
    model = UserApplication
    success_url = reverse_lazy('application_submitted')
    template_name = 'accounts/apply.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            "Your application has been submitted successfully! "
            "You will receive an email notification once it has been reviewed."
        )
        # self.object is the freshly-saved UserApplication.
        send_application_submitted_email(self.object)
        return response

class ResearcherApplicationView(BaseApplicationView):
    form_class = ResearcherApplicationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['application_type'] = 'Scholar'
        return context

class StudentApplicationView(BaseApplicationView):
    form_class = StudentApplicationForm

    def form_valid(self, form):
        response = super().form_valid(form)
        # Let the named advisor know they can review it without an admin.
        send_advisor_review_email(self.object)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['application_type'] = 'Student'
        return context

class ApplicationSubmittedView(View):
    template_name = "accounts/application_submitted.html"

    def get(self, request):
        return render(request, self.template_name)

class CustomLoginView(LoginView):
    model = CustomUser
    form_class = CustomLoginForm
    success_url = reverse_lazy("/")
    template_name = "registration/login.html"


class ProfileView(View):
    template_name = "accounts/profile.html"

    def get(self, request, pk=None):
        if pk:
            try:
                profile_user = CustomUser.objects.get(pk=pk)
            except CustomUser.DoesNotExist:
                raise Http404("User not found")
        else:
            if not request.user.is_authenticated:
                return redirect("login")
            profile_user = request.user

        authored_publications = self._visible(
            Publication.objects.filter(authors__user=profile_user),
            request,
            profile_user,
        ).distinct().select_related("revision_of").prefetch_related("author_links__author__user")

        # Visits the member posted. ``posted_by`` is the only link from a visit
        # back to a member, and the submission form labels the visitor fields
        # "Your Name"/"Your Email", so the poster is normally the visitor.
        visits = self._visible(
            Seminar.objects.filter(posted_by=profile_user),
            request,
            profile_user,
        ).select_related("university").order_by("visit_start", "id")

        events = self._visible(
            Event.objects.filter(host=profile_user),
            request,
            profile_user,
        ).order_by("date", "id")

        jobs = self._visible(
            Job.objects.filter(uploader=profile_user),
            request,
            profile_user,
        ).order_by("deadline", "id")

        return render(request, self.template_name, {
            'profile_user': profile_user,
            'user_profile': profile_user.profile,
            'publications': authored_publications,
            'visits': visits,
            'events': events,
            'jobs': jobs,
            'is_own_profile': request.user.is_authenticated and request.user == profile_user,
        })

    @staticmethod
    def _visible(queryset, request, profile_user):
        """Limit moderated content to what this viewer may see.

        Everyone sees approved items. On your own profile you also see your
        still-pending submissions, so a paper or visit does not silently vanish
        between submitting it and an admin approving it. Rejected items are never
        shown.
        """
        if request.user.is_authenticated and request.user == profile_user:
            return queryset.exclude(status=ApprovalStatus.REJECTED)
        return queryset.filter(status=ApprovalStatus.APPROVED)


class EditProfileView(LoginRequiredMixin, UpdateView):
    model = Profile
    form_class = UpdateProfileForm
    template_name = "accounts/edit_profile.html"

    def get_object(self, **kwargs):
        return self.request.user.profile

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        profile_form = self.get_form()

        if profile_form.is_valid():
            profile = profile_form.save(commit=False)

            if 'avatar' in request.FILES:
                profile.avatar = process_avatar(
                    request.FILES['avatar'], crop=profile_form.cleaned_data.get('avatar_crop'))
            raw_interests = self.request.POST.get('research_interests_input') or '[]'
            profile.research_interests = handle_keywords(raw_interests)

            profile.save()
            messages.success(request, "Profile updated successfully")
            return redirect("profile")

        return self.render_to_response(self.get_context_data(form=profile_form))

class SettingsView(LoginRequiredMixin, View):
    template_name = "accounts/settings.html"

    def get(self, request):
        return render(request, self.template_name, self._context(request))

    def _context(self, request, user_form=None, email_prefs_form=None, alert_prefs_form=None):
        return {
            "user_form": user_form if user_form is not None
            else UpdateUserForm(instance=request.user),
            "email_prefs_form": email_prefs_form if email_prefs_form is not None
            else EmailPreferencesForm(instance=request.user.profile),
            "alert_prefs_form": alert_prefs_form if alert_prefs_form is not None
            else AlertPreferencesForm(instance=request.user.profile),
            # Whitelists for the two Tagify pill inputs in the Alerts section.
            "alert_topic_choices": RECOMMENDED_KEYWORDS,
            "alert_country_choices": [
                {"value": code, "label": label} for code, label in COUNTRY_CHOICES
            ],
            # Only the already-saved institutions; the rest are searched on
            # demand (seminars:university-search) -- never the full table.
            "alert_university_choices": [
                {"value": str(u.pk), "label": university_label(u)}
                for u in University.objects.filter(
                    pk__in=request.user.profile.alert_universities)
            ],
            "saved": request.GET.get("saved"),
        }

    def post(self, request):
        if "save_account" in request.POST:
            user_form = UpdateUserForm(request.POST, instance=request.user)
            if user_form.is_valid():
                user_form.save()
                return redirect(f"{reverse('settings')}?saved=account")
            return render(request, self.template_name,
                          self._context(request, user_form=user_form))

        if "save_notifications" in request.POST:
            email_prefs_form = EmailPreferencesForm(
                request.POST, instance=request.user.profile)
            if email_prefs_form.is_valid():
                # An explicit choice on this page may turn a list back on, which
                # (unlike a routine sync) is allowed to resubscribe in Campaign Monitor.
                request.user.profile.cm_resubscribe = {"newsletter"}
                email_prefs_form.save()
                return redirect(f"{reverse('settings')}?saved=notifications")
            return render(request, self.template_name,
                          self._context(request, email_prefs_form=email_prefs_form))

        if "save_alerts" in request.POST:
            alert_prefs_form = AlertPreferencesForm(
                request.POST, instance=request.user.profile)
            if alert_prefs_form.is_valid():
                request.user.profile.cm_resubscribe = {"alerts"}
                alert_prefs_form.save()
                return redirect(f"{reverse('settings')}?saved=alerts")
            return render(request, self.template_name,
                          self._context(request, alert_prefs_form=alert_prefs_form))

        return redirect("settings")


class AdviseeApplicationsView(LoginRequiredMixin, ListView):
    """Student applications naming the logged-in researcher as advisor.

    Advisors approve or decline their own advisees here without ever touching
    the admin. Staff keep the admin path for every application.
    """
    template_name = "accounts/advisee_applications.html"
    context_object_name = "applications"
    paginate_by = 12

    def get_queryset(self):
        return (
            UserApplication.objects.filter(
                advisor=self.request.user,
                role=CustomUser.Role.STUDENT,
            )
            .select_related("advisor", "university")
            .annotate(
                _pending_first=Case(
                    When(status=UserApplication.Status.PENDING, then=0),
                    default=1,
                    output_field=IntegerField(),
                )
            )
            .order_by("_pending_first", "-applied_at")
        )


def _get_own_advisee(request, pk):
    """Fetch a student application this user advises, or 404.

    The advisor filter *is* the authorization check, so a wrong advisor gets a
    plain 404 and learns nothing about whether the row exists.
    """
    return get_object_or_404(
        UserApplication,
        pk=pk,
        advisor=request.user,
        role=CustomUser.Role.STUDENT,
    )


@login_required
@require_GET
def advisee_paper(request, pk):
    """A research sample attached to an application, for that application's advisor
    (and staff). The bucket has no public address, so Django streams the file."""
    sample = get_object_or_404(ResearchPaper, pk=pk)
    if not (request.user.is_staff or sample.application.advisor_id == request.user.pk):
        raise Http404
    return FileResponse(sample.paper.open('rb'), content_type='application/pdf')


@login_required
@require_POST
def advisee_approve(request, pk):
    application = _get_own_advisee(request, pk)
    if application.status != UserApplication.Status.PENDING:
        messages.error(request, "This application has already been reviewed.")
    else:
        try:
            user = application.approve(admin_user=request.user, advisor=request.user)
            messages.success(
                request,
                f"Approved. An account has been created for {user.email}.",
            )
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect("advisee_applications")


@login_required
@require_POST
def advisee_reject(request, pk):
    application = _get_own_advisee(request, pk)
    if application.status != UserApplication.Status.PENDING:
        messages.error(request, "This application has already been reviewed.")
    else:
        application.reject(request.user)
        messages.success(
            request,
            f"Declined the application from {application.email}.",
        )
    return redirect("advisee_applications")


@require_GET
def newsletter_unsubscribe(request, token):
    """One-click unsubscribe link from newsletter emails sent before Campaign Monitor
    (signed token; see accounts.unsubscribe)."""
    uid = read_newsletter_unsubscribe_token(token)
    profile = None
    if uid is not None:
        profile = Profile.objects.filter(user_id=uid).first()

    if profile is not None:
        if profile.newsletter_frequency != Profile.NewsletterFrequency.OFF:
            profile.newsletter_frequency = Profile.NewsletterFrequency.OFF
            profile.save(update_fields=["newsletter_frequency"])
        return render(request, "accounts/newsletter_unsubscribe.html", {"success": True})

    return render(request, "accounts/newsletter_unsubscribe.html", {"success": False})


@require_GET
def alerts_unsubscribe(request, token):
    """One-click unsubscribe link from alert emails (signed token).

    Separate from newsletter_unsubscribe: it reads a token signed with
    accounts.alerts's own salt and clears the alert lists
    rather than newsletter_frequency, so each unsubscribe link only turns off
    the kind of email it came from.
    """
    uid = read_alert_unsubscribe_token(token)
    profile = None
    if uid is not None:
        profile = Profile.objects.filter(user_id=uid).first()

    if profile is not None:
        if profile.alert_topics or profile.alert_countries or profile.alert_universities:
            profile.alert_topics = []
            profile.alert_countries = []
            profile.alert_universities = []
            profile.save(update_fields=[
                "alert_topics", "alert_countries", "alert_universities"])
        return render(request, "accounts/alerts_unsubscribe.html", {"success": True})

    return render(request, "accounts/alerts_unsubscribe.html", {"success": False})
