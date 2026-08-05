from django.contrib import admin

from core.admin import ApprovableAdmin

from .models import Event


@admin.register(Event)
class EventAdmin(ApprovableAdmin):
    list_display = ['title', 'date', 'deadline', 'location', 'category', 'host']
    list_filter = ['category', 'created_at']
    search_fields = ['title', 'description', 'location', 'host__first_name', 'host__last_name']
    readonly_fields = ['created_at']

    fieldsets = (
        ('Event Information', {
            'fields': ('title', 'description', 'date', 'end_date', 'deadline',
                       'location', 'category', 'host')
        }),
        ('Review', {
            'fields': ('review_actions', 'status', 'admin_notes', 'created_at',
                       'reviewed_at', 'reviewed_by')
        }),
    )
