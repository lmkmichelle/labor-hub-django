from django.http import HttpResponseRedirect
from django.urls import path
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html

from .models import Profile, CustomUser, UserApplication


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser',
                                    'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    list_display = ('email', 'first_name', 'last_name', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)


@admin.register(UserApplication)
class UserApplicationAdmin(admin.ModelAdmin):
    list_display = [
        "email",
        "first_name",
        "last_name",
        'status',
        'account_actions',
        'applied_at',
        'reviewed_by'
    ]

    list_filter = ['status', 'applied_at']
    search_fields = ['email', 'first_name', 'last_name']
    readonly_fields = ['applied_at', 'reviewed_at', 'reviewed_by', 'account_actions']
    ordering = ['-applied_at']

    fieldsets = (
        ('Application Info', {
            'fields': ('email', 'first_name', 'last_name', 'position', 'education', 'country_code', 'motivation')
        }),
        ('Review', {
            'fields': ('admin_notes', 'account_actions', 'applied_at', 'reviewed_at', 'reviewed_by')
        }),
    )

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
                except ValueError as e:
                    messages.error(request, f'Error approving application: {str(e)}')

        except UserApplication.DoesNotExist:
            messages.error(request, 'Application not found.')

        except Exception as e:
            messages.error(request, f'Error approving application: {str(e)}')

        return HttpResponseRedirect(reverse('admin:accounts_userapplication_changelist'))

    def reject_application(self, request, application_id):
        try:
            application = UserApplication.objects.get(pk=application_id)
            if application.status != 'pending':
                messages.error(request, 'This application has already been reviewed.')

            else:
                application.reject(request.user)
                messages.success(
                    request,
                    f'Application rejected for {application.email}'
                )
        except UserApplication.DoesNotExist:
            messages.error(request, 'Application not found.')

        except Exception as e:
            messages.error(request, f'Error rejecting application: {str(e)}')

        return HttpResponseRedirect(reverse('admin:accounts_userapplication_changelist'))

    def account_actions(self, obj):
        if obj.status == 'pending':
            return format_html(
                '<a class="button" href="{}">Approve</a>&nbsp;'
                '<a class="button" href="{}">Deny</a>',
                reverse('admin:approve_application', args=[obj.pk]),
                reverse('admin:reject_application', args=[obj.pk])
            )
        else:
            return format_html(
                '<span style="color: #666; font-style: italic;">Status: {}</span>',
                obj.get_status_display()
            )

    account_actions.short_description = 'Approve/Deny Application'
    account_actions.allow_tags = True

admin.site.register(CustomUser, UserAdmin)
admin.site.register(Profile)
