from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils import timezone

from .models import Event


class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'date', 'location', 'category', 'host', 'status', 'account_actions']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['title', 'description', 'location', 'host__first_name', 'host__last_name']
    readonly_fields = ['account_actions', 'created_at', 'reviewed_at', 'reviewed_by']

    fieldsets = (
        ('Event Information', {
            'fields': ('title', 'description', 'date', 'end_date', 'location', 'category', 'host')
        }),
        ('Review Status', {
            'fields': ('status', 'account_actions', 'created_at', 'reviewed_at', 'reviewed_by')
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:event_id>/approve/',
                self.admin_site.admin_view(self.approve_event),
                name='approve_event',
            ),
            path(
                '<int:event_id>/reject/',
                self.admin_site.admin_view(self.reject_event),
                name='reject_event',
            ),
        ]
        return custom_urls + urls

    def approve_event(self, request, event_id):
        event = Event.objects.get(pk=event_id)
        event.status = 'approved'
        event.reviewed_at = timezone.now()
        event.reviewed_by = request.user
        event.save()

        messages.success(request, f'Event "{event.title}" has been approved.')
        return HttpResponseRedirect(reverse('admin:events_event_changelist'))

    def reject_event(self, request, event_id):
        event = Event.objects.get(pk=event_id)
        event.status = 'rejected'
        event.reviewed_at = timezone.now()
        event.reviewed_by = request.user
        event.save()

        messages.warning(request, f'Event "{event.title}" has been rejected.')
        return HttpResponseRedirect(reverse('admin:events_event_changelist'))

    def account_actions(self, obj):
        if not obj.pk:
            return '-'
        
        if obj.status == 'pending':
            approve_url = reverse('admin:approve_event', args=[obj.pk])
            reject_url = reverse('admin:reject_event', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}">Approve</a> '
                '<a class="button" href="{}" style="margin-left:10px;">Reject</a>',
                approve_url, reject_url
            )
        elif obj.status == 'approved':
            return format_html('<span style="color: green;">✓ Approved</span>')
        else:
            return format_html('<span style="color: red;">✗ Rejected</span>')

    account_actions.short_description = 'Actions'
    account_actions.allow_tags = True


admin.site.register(Event, EventAdmin)
