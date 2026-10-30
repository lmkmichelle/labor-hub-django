import logging

from datetime import timedelta

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from core import cm_lists
from core.models import ApprovalStatus, EmailCampaign, NewsletterSchedule
from core.newsletter import KINDS, last_sent_issue, newsletter_context, render_newsletter
from .models import ContactMessage

logger = logging.getLogger(__name__)


class ApprovableAdmin(admin.ModelAdmin):
    """Admin mixin for models inheriting :class:`core.models.Approvable`.

    Provides the moderation workflow once so each concrete admin only declares
    its own domain fields: bulk approve/reject actions, per-row Approve/Reject
    buttons, a ``status`` column + filter, and read-only review audit fields.
    """

    actions = ('approve_selected', 'reject_selected')
    review_readonly_fields = ('reviewed_at', 'reviewed_by')

    def get_list_display(self, request):
        list_display = list(super().get_list_display(request))
        for field in ('status', 'review_actions'):
            if field not in list_display:
                list_display.append(field)
        return list_display

    def get_list_filter(self, request):
        list_filter = list(super().get_list_filter(request))
        if 'status' not in list_filter:
            list_filter = ['status', *list_filter]
        return list_filter

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        for field in (*self.review_readonly_fields, 'review_actions'):
            if field not in readonly:
                readonly.append(field)
        return readonly

    def save_model(self, request, obj, form, change):
        # `status` is directly editable in the change form (so an admin can,
        # say, revert an approved item to pending), which means flipping it
        # to approved/rejected there and clicking Save would otherwise call
        # obj.save() directly -- bypassing approve()/reject() entirely, so
        # reviewed_at/reviewed_by never get set and a subclass's side effects
        # (e.g. Publication assigning a discussion_paper_number and building
        # its cover PDF) silently never fire. Route that one transition
        # through the real method instead, exactly as the Approve/Reject
        # buttons do; every other save (add, or edit with no pending ->
        # approved/rejected transition) is untouched.
        if (
            change
            and 'status' in form.changed_data
            and form.initial.get('status') == ApprovalStatus.PENDING
            and obj.status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED)
        ):
            target_status = obj.status
            obj.status = ApprovalStatus.PENDING
            if target_status == ApprovalStatus.APPROVED:
                obj.approve(request.user)
            else:
                obj.reject(request.user)
            return
        super().save_model(request, obj, form, change)

    # -- bulk actions ---------------------------------------------------------
    @admin.action(description="Approve selected pending items")
    def approve_selected(self, request, queryset):
        updated = self._bulk_review(request, queryset, approve=True)
        self.message_user(request, f"{updated} item(s) approved.", messages.SUCCESS)

    @admin.action(description="Reject selected pending items")
    def reject_selected(self, request, queryset):
        updated = self._bulk_review(request, queryset, approve=False)
        self.message_user(request, f"{updated} item(s) rejected.", messages.WARNING)

    def _bulk_review(self, request, queryset, approve):
        updated = 0
        for obj in queryset.filter(status=ApprovalStatus.PENDING):
            obj.approve(request.user) if approve else obj.reject(request.user)
            updated += 1
        return updated

    # -- per-row buttons ------------------------------------------------------
    def _action_url_name(self, action):
        meta = self.model._meta
        return f"{meta.app_label}_{meta.model_name}_{action}"

    def get_urls(self):
        custom = [
            path(
                '<int:pk>/approve/',
                self.admin_site.admin_view(self.process_approve),
                name=self._action_url_name('approve'),
            ),
            path(
                '<int:pk>/reject/',
                self.admin_site.admin_view(self.process_reject),
                name=self._action_url_name('reject'),
            ),
        ]
        return custom + super().get_urls()

    def _changelist_redirect(self):
        meta = self.model._meta
        return HttpResponseRedirect(
            reverse(f"admin:{meta.app_label}_{meta.model_name}_changelist")
        )

    def _process_review(self, request, pk, approve):
        try:
            obj = self.model.objects.get(pk=pk)
        except self.model.DoesNotExist:
            self.message_user(request, "Item not found.", messages.ERROR)
            return self._changelist_redirect()
        try:
            if approve:
                obj.approve(request.user)
                self.message_user(request, "Item approved.", messages.SUCCESS)
            else:
                obj.reject(request.user)
                self.message_user(request, "Item rejected.", messages.WARNING)
        except ValueError as exc:
            self.message_user(request, str(exc), messages.ERROR)
        except Exception as exc:
            # e.g. the cover could not be built. approve() is all-or-nothing, so the
            # item is still pending and can simply be approved again.
            logger.exception("Could not %s %s %s", "approve" if approve else "reject",
                             self.model.__name__, pk)
            self.message_user(
                request,
                f"Could not {'approve' if approve else 'reject'} this item ({exc}). "
                "It was left pending; nothing was changed.",
                messages.ERROR)
        return self._changelist_redirect()

    def process_approve(self, request, pk):
        return self._process_review(request, pk, approve=True)

    def process_reject(self, request, pk):
        return self._process_review(request, pk, approve=False)

    @admin.display(description="Review")
    def review_actions(self, obj):
        if not obj or not obj.pk:
            return format_html(
                '<span style="color:#666;font-style:italic;">Save to see actions</span>'
            )
        if obj.status == ApprovalStatus.PENDING:
            return format_html(
                '<a class="button" href="{}">Approve</a>&nbsp;'
                '<a class="button" href="{}">Reject</a>',
                reverse(f"admin:{self._action_url_name('approve')}", args=[obj.pk]),
                reverse(f"admin:{self._action_url_name('reject')}", args=[obj.pk]),
            )
        return format_html(
            '<span style="color:#666;font-style:italic;">Status: {}</span>',
            obj.get_status_display(),
        )


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'created_at', 'handled')
    list_filter = ('handled', 'created_at')
    list_editable = ('handled',)
    search_fields = ('name', 'email', 'message')
    readonly_fields = ('name', 'email', 'message', 'created_at')
    ordering = ('-created_at',)


@admin.register(NewsletterSchedule)
class NewsletterScheduleAdmin(admin.ModelAdmin):
    """The Newsletters page: what the next weekly and monthly issues will contain, and
    pause / preview / test / send-now controls, so admins run the newsletter themselves.

    The list view is replaced by a dashboard; the two schedule rows are created on
    demand, so adding and deleting are hidden."""

    # Two sends of the same kind this close together are refused, even when confirmed.
    DOUBLE_SEND_GUARD = timedelta(minutes=10)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        name = self._url_name
        wrap = self.admin_site.admin_view
        return [
            path('<str:kind>/toggle/', wrap(self.toggle_view), name=name('toggle')),
            path('<str:kind>/preview/', wrap(self.preview_view), name=name('preview')),
            path('<str:kind>/test/', wrap(self.test_view), name=name('test')),
            path('<str:kind>/send/', wrap(self.send_view), name=name('send')),
        ] + super().get_urls()

    @staticmethod
    def _url_name(action):
        return f"core_newsletterschedule_{action}"

    # -- helpers --------------------------------------------------------------
    def _kind(self, kind):
        if kind not in KINDS:
            raise Http404
        return kind

    def _require_change(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied

    def _back(self):
        return HttpResponseRedirect(reverse("admin:core_newsletterschedule_changelist"))

    def _cm_ready(self):
        from django.conf import settings
        return bool(settings.CM_API_KEY and settings.CM_CLIENT_ID
                    and cm_lists.list_id(cm_lists.NEWSLETTER))

    def _subscribers(self, kind):
        from accounts.models import Profile
        return Profile.objects.filter(newsletter_frequency=kind, user__is_active=True).count()

    def _recently_sent(self, kind, now=None):
        last = last_sent_issue(kind)
        now = now or timezone.now()
        return last if last and last.sent_at and now - last.sent_at < KINDS[kind]["guard"] else None

    def _panel(self, request, kind, now):
        from accounts.campaigns import newsletter_due
        schedule = NewsletterSchedule.for_kind(kind)
        context = newsletter_context(kind, now)
        due, reason = newsletter_due(kind, now)
        listed = {key: context[f"all_{key}"] for key in ("events", "special_issues", "jobs")}
        sections = [(key.replace("_", " ").capitalize(), items) for key, items in listed.items()]
        return {
            "kind": kind, "label": KINDS[kind]["label"], "schedule": schedule,
            "context": context, "due": due, "skip_reason": reason,
            "last": last_sent_issue(kind), "subscribers": self._subscribers(kind),
            "sections": sections, "max_listed": context["max_listed"],
            "empty": not (context["papers"] or any(listed.values())),
        }

    # -- views ----------------------------------------------------------------
    def changelist_view(self, request, extra_context=None):
        if not self.has_view_permission(request):
            raise PermissionDenied
        now = timezone.now()
        history = EmailCampaign.objects.filter(
            kind__in=[spec["campaign_kind"] for spec in KINDS.values()],
            status=EmailCampaign.Status.SENT).order_by("-sent_at", "-created_at")[:10]
        return render(request, "admin/core/newsletter_dashboard.html", {
            **self.admin_site.each_context(request),
            "opts": self.model._meta, "title": "Newsletters",
            "panels": [self._panel(request, kind, now) for kind in KINDS],
            "history": history, "cm_ready": self._cm_ready(),
            "can_change": self.has_change_permission(request),
        })

    def toggle_view(self, request, kind):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        self._require_change(request)
        schedule = NewsletterSchedule.for_kind(self._kind(kind))
        schedule.set_paused(not schedule.paused, request.user)
        self.message_user(
            request, f"The {schedule.get_kind_display().lower()} newsletter is now "
                     f"{'paused: scheduled sends skip it' if schedule.paused else 'active again'}.",
            messages.WARNING if schedule.paused else messages.SUCCESS)
        return self._back()

    def preview_view(self, request, kind):
        if not self.has_view_permission(request):
            raise PermissionDenied
        html, _ = render_newsletter(newsletter_context(self._kind(kind)))
        return HttpResponse(html)

    def _cm_guard(self, request, kind):
        """A redirect (with an error) when sending is not possible, else ``None``."""
        if not self._cm_ready():
            self.message_user(request, "Campaign Monitor is not set up, so nothing can be sent.",
                              messages.ERROR)
            return self._back()
        return None

    def test_view(self, request, kind):
        from accounts.campaigns import preview_newsletter_issue
        from core.campaign_monitor import CampaignMonitorError
        self._require_change(request)
        self._kind(kind)
        blocked = self._cm_guard(request, kind)
        if blocked:
            return blocked
        error = ""
        value = request.POST.get("addresses", request.user.email)
        if request.method == "POST":
            addresses = [a.strip() for a in value.split(",") if a.strip()]
            if not 1 <= len(addresses) <= 5:
                error = "Enter 1 to 5 email addresses, separated by commas."
            else:
                try:
                    campaign = preview_newsletter_issue(kind, addresses)
                except CampaignMonitorError as exc:
                    error = f"Campaign Monitor error: {exc}"
                else:
                    self.message_user(
                        request, f"Preview of '{campaign.subject}' sent to {', '.join(addresses)}.",
                        messages.SUCCESS)
                    return self._back()
        return render(request, "admin/core/newsletter_test.html", {
            **self.admin_site.each_context(request), "opts": self.model._meta,
            "title": f"Send a test of the {KINDS[kind]['label'].lower()} newsletter",
            "kind": kind, "value": value, "error": error})

    def send_view(self, request, kind):
        from accounts.campaigns import send_newsletter_issue
        from core.campaign_monitor import CampaignMonitorError
        self._require_change(request)
        self._kind(kind)
        blocked = self._cm_guard(request, kind)
        if blocked:
            return blocked
        now = timezone.now()
        recent = self._recently_sent(kind, now)
        context = newsletter_context(kind, now)
        error = ""
        if request.method == "POST":
            last = last_sent_issue(kind)
            if last and last.sent_at and now - last.sent_at < self.DOUBLE_SEND_GUARD:
                error = "This newsletter was sent a moment ago, so it was not sent again."
            elif recent and not request.POST.get("send_anyway"):
                error = "Tick the box to confirm sending again."
            else:
                try:
                    campaign = send_newsletter_issue(kind, now=now)
                except (CampaignMonitorError, RuntimeError) as exc:
                    error = f"Not sent: {exc}"
                else:
                    self.message_user(request, f"Sent '{campaign.subject}' to "
                                      f"{self._subscribers(kind)} subscribers.", messages.SUCCESS)
                    return self._back()
        return render(request, "admin/core/newsletter_send.html", {
            **self.admin_site.each_context(request), "opts": self.model._meta,
            "title": f"Send the {KINDS[kind]['label'].lower()} newsletter now",
            "kind": kind, "subject": context["subject"], "recent": recent,
            "subscribers": self._subscribers(kind), "error": error,
            "empty": not (context["papers"] or context["all_events"]
                          or context["all_special_issues"] or context["all_jobs"]),
        })
