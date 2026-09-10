from django.contrib import admin

from core.admin import ApprovableAdmin

from .models import Author, Publication


class AuthorInline(admin.TabularInline):
    model = Publication.authors.through
    extra = 1
    autocomplete_fields = ['author']


class AuthorAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'user', 'name']
    search_fields = ['name', 'user__first_name', 'user__last_name']


class PublicationAdmin(ApprovableAdmin):
    inlines = [AuthorInline]
    list_display = ['title', 'applied_at', 'country_code', 'is_job_market',
                    'jm_advisor', 'jm_advisor_acknowledged']
    search_fields = ['title', 'abstract']
    list_filter = ['applied_at', 'is_job_market', 'jm_advisor_acknowledged']
    readonly_fields = ['applied_at', 'submitted_by', 'jm_advisor_responded_at']
    autocomplete_fields = ['jm_advisor']

    fieldsets = (
        ('Publication Info', {
            'fields': ('title', 'authors', 'abstract', 'country_code',
                       'topic', 'is_job_market', 'pdf', 'submitted_by')
        }),
        ('Job market advisor', {
            'fields': ('jm_advisor', 'jm_advisor_acknowledged',
                       'jm_advisor_responded_at')
        }),
        ('Review', {
            'fields': ('review_actions', 'status', 'admin_notes', 'applied_at',
                       'reviewed_at', 'reviewed_by')
        }),
    )


admin.site.register(Publication, PublicationAdmin)
admin.site.register(Author, AuthorAdmin)
