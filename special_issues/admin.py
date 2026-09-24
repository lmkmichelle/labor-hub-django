from django.contrib import admin

from core.admin import ApprovableAdmin

from .models import SpecialIssue


class SpecialIssueAdmin(ApprovableAdmin):
    list_display = ['title', 'journal', 'submission_deadline', 'posted_by']
    search_fields = ['title', 'journal', 'description']
    list_filter = ['submission_deadline']

    fieldsets = (
        ('Special Issue', {
            'fields': (
                'posted_by',
                'journal',
                'title',
                'description',
                'call_url',
                'submission_deadline',
                'editors',
            )
        }),
        ('Review', {
            'fields': ('review_actions', 'status', 'admin_notes', 'reviewed_at', 'reviewed_by')
        }),
    )


admin.site.register(SpecialIssue, SpecialIssueAdmin)
