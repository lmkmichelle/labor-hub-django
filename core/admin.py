from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from core.models import ApprovalStatus
from .models import ContactMessage


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
