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
    list_display = ['title', 'number_display', 'applied_at', 'country_code',
                    'is_job_market', 'jm_advisor', 'jm_advisor_acknowledged']
    search_fields = ['title', 'abstract']
    list_filter = ['applied_at', 'is_job_market', 'jm_advisor_acknowledged']
    readonly_fields = ['applied_at', 'submitted_by', 'jm_advisor_responded_at',
                       'discussion_paper_number', 'job_market_paper_number', 'pdf_original']
    autocomplete_fields = ['jm_advisor']
    actions = ApprovableAdmin.actions + ('regenerate_cover',)

    fieldsets = (
        ('Publication Info', {
            'fields': ('title', 'authors', 'abstract', 'country_code',
                       'topic', 'is_job_market', 'discussion_paper_number',
                       'job_market_paper_number', 'pdf_original', 'pdf', 'submitted_by')
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

    @admin.display(description="No.")
    def number_display(self, obj):
        return obj.display_number or "—"

    @admin.action(description="Regenerate the cover page for selected papers")
    def regenerate_cover(self, request, queryset):
        updated = 0
        for publication in queryset:
            if publication.display_number is not None:
                publication.rebuild_covered_pdf()
                updated += 1
        self.message_user(request, f"Regenerated the cover for {updated} paper(s).")


admin.site.register(Publication, PublicationAdmin)
admin.site.register(Author, AuthorAdmin)
