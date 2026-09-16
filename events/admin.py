from django.contrib import admin

from core.admin import ApprovableAdmin

from .models import Event


@admin.register(Event)
class EventAdmin(ApprovableAdmin):
    list_display = ['title', 'date', 'deadline', 'location', 'category', 'host']
    list_filter = ['category', 'created_at']
    search_fields = ['title', 'description', 'location', 'city', 'host__first_name', 'host__last_name']
    # location is derived from country_code/city/venue on save() (see
    # Event.save()) once any of those are set, so it's shown but not directly
    # editable here to avoid a manual edit being silently overwritten.
    readonly_fields = ['created_at', 'location']

    fieldsets = (
        ('Event Information', {
            'fields': ('title', 'description', 'date', 'end_date', 'deadline',
                       'application_url', 'country_code', 'city', 'venue',
                       'location', 'category', 'host')
        }),
        ('Review', {
            'fields': ('review_actions', 'status', 'admin_notes', 'created_at',
                       'reviewed_at', 'reviewed_by')
        }),
    )
