from django.http import HttpResponseRedirect
from django.urls import path
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import format_html

from .models import Profile, CustomUser, UserApplication, ResearchPaper


# Colours mirror the site's .pill-* roles (accent red for students). Inline
# style is used because the Django admin changelist has no template hook and
# djlint only lints templates, not admin.py.
_ROLE_BADGE_COLOURS = {
    CustomUser.Role.STUDENT: ('#b91c1c', '#fee2e2'),
    CustomUser.Role.RESEARCHER: ('#1f2937', '#e5e7eb'),
    CustomUser.Role.ADMIN: ('#92400e', '#fef3c7'),
}


def _role_badge(role, label):
    fg, bg = _ROLE_BADGE_COLOURS.get(role, ('#1f2937', '#e5e7eb'))
    return format_html(
        '<span style="display:inline-block; padding:2px 8px; border-radius:9999px; '
        'font-size:11px; font-weight:600; color:{}; background:{};">{}</span>',
        fg, bg, label,
    )


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


class ResearchPaperInline(admin.TabularInline):
    model = ResearchPaper
    extra = 1
    max_num = 2
    can_delete = True
    fields = ['paper', 'uploaded_at']
    readonly_fields = ['uploaded_at']


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'role', 'is_staff', 'is_superuser',
                                    'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    list_display = ('email', 'first_name', 'last_name', 'role_badge', 'is_staff')
    list_filter = BaseUserAdmin.list_filter + ('role',)
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)

    @admin.display(description='Role', ordering='role')
    def role_badge(self, obj):
        return _role_badge(obj.role, obj.get_role_display())


@admin.register(UserApplication)
class UserApplicationAdmin(admin.ModelAdmin):
    inlines = [ResearchPaperInline]
    list_display = [
        "email",
        "first_name",
        "last_name",
        'role_badge',
        'advisor_display',
        'status_display',
        'cv_link_display',
        'account_actions',
        'applied_at',
        'reviewed_by'
    ]

    list_filter = ['status', 'role', 'applied_at']
    list_select_related = ['advisor', 'reviewed_by']
    # 10k universities: a search box, not a 10k-option <select>.
    autocomplete_fields = ['university']
    search_fields = ['email', 'first_name', 'last_name']
    readonly_fields = ['applied_at', 'reviewed_at', 'reviewed_by', 'account_actions', 'resume', 'cv_link_display', 'other_networks',
                       'returning_account_note', 'uploaded_files_note', 'rejection_message_display']
    ordering = ['-applied_at']

    fieldsets = (
        ('Application Info', {
            'fields': ('email', 'first_name', 'last_name', 'role', 'position', 'department', 'university', 'university_name',
                       'country_code', 'website', 'cv_url', 'other_networks', 'motivation', 'advisor',
                       'previous_student_account', 'previous_jm_paper_number', 'returning_account_note')
        }),
        ('Review', {
            'fields': ('cv_link_display', 'resume', 'uploaded_files_note', 'rejection_message_display', 'admin_notes', 'account_actions', 'applied_at', 'reviewed_at', 'reviewed_by')
        }),
    )

    @admin.display(description='Role', ordering='role')
    def role_badge(self, obj):
        return _role_badge(obj.role, obj.get_role_display())

    @admin.display(description='CV')
    def cv_link_display(self, obj):
        if not obj.cv_url:
            return '—'
        return format_html('<a href="{}" target="_blank" rel="noopener">CV link</a>', obj.cv_url)

    @admin.display(description='Advisor', ordering='advisor__last_name')
    def advisor_display(self, obj):
        return obj.advisor.get_full_name() if obj.advisor else '-'

    @admin.display(description='Status', ordering='status')
    def status_display(self, obj):
        # The named advisor approves students; admins need not act on them.
        if obj.status == 'pending' and obj.role == CustomUser.Role.STUDENT and obj.advisor:
            return 'Awaiting advisor'
        return obj.get_status_display()

    @admin.display(description='Existing account')
    def returning_account_note(self, obj):
        """Tell the reviewer approving will upgrade a former student's account,
        and show which job market paper (if any) the applicant is claiming."""
        notes = []
        if obj.pk and obj.status == 'pending' and obj.returning_student() is not None:
            notes.append('A deactivated student account uses this email. Approving reactivates '
                         'it as a scholar account, keeping all of its papers and posts.')
        if obj.previous_student_account and obj.previous_jm_paper_number:
            from publications.models import Publication
            paper = Publication.find_original(obj.previous_jm_paper_number, job_market_only=True)
            if paper is None:
                notes.append(f'Claimed job market paper {obj.previous_jm_paper_number}: not found.')
            else:
                authors = ', '.join(a.name or a.user.get_full_name() for a in paper.authors.select_related('user'))
                notes.append(f'Claimed job market paper {paper.display_number}: {paper.title} ({authors}).')
        return ' '.join(notes) or '-'

    @admin.display(description='Message sent')
    def rejection_message_display(self, obj):
        return obj.rejection_message or '-'

    @admin.display(description='Uploaded files')
    def uploaded_files_note(self, obj):
        """When the samples and resume are (or were) deleted."""
        from accounts.models import REJECTED_FILE_RETENTION
        if not obj.pk:
            return '-'
        if obj.files_purged_at:
            return f'Deleted on {obj.files_purged_at:%b %-d, %Y}.'
        if obj.status == 'rejected' and obj.reviewed_at:
            return f'Kept until {obj.reviewed_at + REJECTED_FILE_RETENTION:%b %-d, %Y} (30 days after rejection).'
        if obj.status == 'pending':
            return 'Kept while pending; the samples are deleted on approval.'
        return 'Samples are deleted on approval.'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:application_id>/approve/',
                self.admin_site.admin_view(self.approve_application),
                name='approve_application',
            ),
            path(
                '<int:application_id>/reject/',
                self.admin_site.admin_view(self.reject_application),
                name='reject_application',
            ),
            path(
                '<int:application_id>/undo-rejection/',
                self.admin_site.admin_view(self.undo_rejection),
                name='undo_rejection_application',
            ),
        ]
        return custom_urls + urls

    def approve_application(self, request, application_id):
        try:
            application = UserApplication.objects.get(pk=application_id)
            if application.status != 'pending':
                messages.error(request, 'This application has already been reviewed.')

            else:
                try:
                    user = application.approve(request.user)
                    messages.success(
                        request,
                        f'Application approved! User account created for {user.email}'
                    )
                    note = getattr(application, 'claim_note', '')
                    if note:
                        messages.warning(request, note)
                except ValueError as e:
                    messages.error(request, f'Error approving application: {str(e)}')

        except UserApplication.DoesNotExist:
            messages.error(request, 'Application not found.')

        except Exception as e:
            messages.error(request, f'Error approving application: {str(e)}')

        return HttpResponseRedirect(reverse('admin:accounts_userapplication_changelist'))

    def reject_application(self, request, application_id):
        """Confirm page: the decline email is shown, editable, before anything is sent."""
        from django.template.response import TemplateResponse
        from accounts.models import rejection_message_presets
        application = get_object_or_404(UserApplication, pk=application_id)
        changelist = reverse('admin:accounts_userapplication_changelist')
        if application.status != 'pending':
            messages.error(request, 'This application has already been reviewed.')
            return HttpResponseRedirect(changelist)
        presets = rejection_message_presets(application)
        error = ''
        if request.method == 'POST':
            message = request.POST.get('message', '').strip()
            if not message:
                error = 'Write a message to send to the applicant.'
            elif len(message) > 5000:
                error = 'The message is too long (5,000 characters at most).'
            else:
                try:
                    application.reject(request.user, message)
                except Exception as e:
                    messages.error(request, f'Error rejecting application: {e}')
                else:
                    messages.success(
                        request, f'Application denied; the message was sent to {application.email}.')
                return HttpResponseRedirect(changelist)
        keys = [key for key, _, _ in presets]
        preset = request.GET.get('preset')
        preset = preset if preset in keys else 'default'
        message = request.POST.get('message') or next(t for k, _, t in presets if k == preset)
        return TemplateResponse(request, 'admin/accounts/userapplication/reject.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Deny application', 'application': application,
            'presets': presets, 'preset': preset, 'message': message, 'error': error,
        })

    def undo_rejection(self, request, application_id):
        try:
            application = UserApplication.objects.get(pk=application_id)
            user = application.undo_rejection(request.user)
            messages.success(
                request,
                f'Rejection undone: account created for {user.email} and the acceptance email sent.'
            )
            note = getattr(application, 'claim_note', '')
            if note:
                messages.warning(request, note)
        except UserApplication.DoesNotExist:
            messages.error(request, 'Application not found.')
        except ValueError as e:
            messages.error(request, f'Could not undo the rejection: {e}')
        except Exception as e:
            messages.error(request, f'Could not undo the rejection: {e}')

        return HttpResponseRedirect(reverse('admin:accounts_userapplication_changelist'))

    def account_actions(self, obj):
        if obj.status == 'pending':
            return format_html(
                '<a class="button" href="{}">Approve</a>&nbsp;'
                '<a class="button" href="{}">Deny</a>',
                reverse('admin:approve_application', args=[obj.pk]),
                reverse('admin:reject_application', args=[obj.pk])
            )
        if obj.status == 'rejected':
            return format_html(
                '<span style="color: #666; font-style: italic;">Status: {}</span><br>'
                '<a class="button" href="{}" style="white-space: nowrap; display: inline-block; margin-top: 8px;" '
                'title="Approve this applicant after all" '
                'onclick="return confirm(\'Approve this applicant? An account is created and the acceptance email is sent.\');">'
                'Undo rejection</a>',
                obj.get_status_display(),
                reverse('admin:undo_rejection_application', args=[obj.pk]),
            )
        return format_html(
            '<span style="color: #666; font-style: italic;">Status: {}</span>',
            obj.get_status_display()
        )

    account_actions.short_description = 'Approve/Deny Application'
    account_actions.allow_tags = True

admin.site.register(CustomUser, UserAdmin)
admin.site.register(Profile)
