from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Publication, Author


class AuthorInline(admin.TabularInline):
    model = Publication.authors.through
    extra = 1
    autocomplete_fields = ['author']

class AuthorAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'user', 'name']
    search_fields = ['name', 'user__first_name', 'user__last_name']

class PublicationAdmin(admin.ModelAdmin):
    inlines = [AuthorInline]
    list_display = ['title', 'date', 'account_actions', 'country_code', 'is_job_market', 'status']
    search_fields = ['title', 'abstract']
    readonly_fields = ['account_actions', 'applied_at', 'reviewed_at', 'reviewed_by']
    list_filter = ['status', 'applied_at']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:publication_id>/approve/',
                self.admin_site.admin_view(self.approve_publication),
                name='approve_publication',
            ),
            path(
                '<int:publication_id>/reject/',
                self.admin_site.admin_view(self.reject_publication),
                name='reject_publication',
            ),
        ]
        return custom_urls + urls

    fieldsets = (
        ('Publication Info', {
            'fields': ('title', 'authors', 'date', 'abstract', 'country_code', 'topic', 'keywords', 'study_url', 'is_job_market', 'pdf')
        }),
        ('Review', {
            'fields': ('account_actions', 'admin_notes', 'applied_at', 'reviewed_at', 'reviewed_by')
        }),
    )

    def approve_publication(self, request, publication_id):
        try:
            publication = Publication.objects.get(pk=publication_id)
            if publication.status != 'pending':
                messages.error(request, 'This application has already been reviewed.')

            else:
                try:
                    user = publication.approve(request.user)
                    messages.success(
                        request,
                        f'Publication approved!'
                    )
                except ValueError as e:
                    messages.error(request, f'Error approving publication: {str(e)}')

        except Publication.DoesNotExist:
            messages.error(request, 'Publication not found.')

        except Exception as e:
            messages.error(request, f'Error approving publication: {str(e)}')

        return HttpResponseRedirect(reverse('admin:publications_publication_changelist'))
    
    def reject_publication(self, request, publication_id):
        try:
            publication = Publication.objects.get(pk=publication_id)
            if publication.status != 'pending':
                messages.error(request, 'This publication has already been reviewed.')

            else:
                publication.reject(request.user)
                messages.success(
                    request,
                    f'Publication rejected for {publication.email}'
                )
        except Publication.DoesNotExist:
            messages.error(request, 'Publication not found.')

        except Exception as e:
            messages.error(request, f'Error rejecting publication: {str(e)}')

        return HttpResponseRedirect(reverse('admin:publications_publication_changelist'))


    def account_actions(self, obj):
        # Avoid reversing URLs with a missing PK on add view
        if not obj or not obj.pk:
            return format_html(
                '<span style="color: #666; font-style: italic;">Save to see actions</span>'
            )

        if obj.status == 'pending':
            return format_html(
                '<a class="button" href="{}">Approve</a>&nbsp;'
                '<a class="button" href="{}">Deny</a>',
                reverse('admin:approve_publication', args=[obj.pk]),
                reverse('admin:reject_publication', args=[obj.pk])
            )
        else:
            return format_html(
                '<span style="color: #666; font-style: italic;">Status: {}</span>',
                obj.get_status_display()
            )

    account_actions.short_description = 'Approve/Deny Publication'
    account_actions.allow_tags = True

admin.site.register(Publication, PublicationAdmin)
admin.site.register(Author, AuthorAdmin)
