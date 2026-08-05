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
    list_display = ['title', 'date', 'country_code', 'is_job_market']
    search_fields = ['title', 'abstract']
    list_filter = ['applied_at']
    readonly_fields = ['applied_at']

    fieldsets = (
        ('Publication Info', {
            'fields': ('title', 'authors', 'date', 'abstract', 'country_code',
                       'topic', 'keywords', 'study_url', 'is_job_market', 'pdf')
        }),
        ('Review', {
            'fields': ('review_actions', 'status', 'admin_notes', 'applied_at',
                       'reviewed_at', 'reviewed_by')
        }),
    )


admin.site.register(Publication, PublicationAdmin)
admin.site.register(Author, AuthorAdmin)
