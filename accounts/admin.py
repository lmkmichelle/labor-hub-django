from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
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
        # "position",
        # "education",
        # "country_code",
        # "motivation",
        'status',
        'applied_at',
        'reviewed_by',
        'account_actions'
    ]

    list_filter = ['status', 'applied_at']
    search_fields = ['email', 'first_name', 'last_name']
    readonly_fields = ['applied_at', 'reviewed_at', 'reviewed_by', 'account_actions']
    ordering = ['-applied_at']

    fieldsets = (
        ('Application Info', {
            'fields': ('email', 'first_name', 'last_name', 'position', 'education', 'country_code')
        }),
        ('Motivation', {
            'fields': ('motivation',)
        }),
        ('Review', {
            'fields': ('status', 'admin_notes', 'applied_at', 'reviewed_at', 'reviewed_by')
        }),
    )

    def account_actions(self, obj):
        return format_html(
            '<a class="button" href="/">Deposit</a>&nbsp;'
            '<a class="button" href="/">Withdraw</a>',
            # reverse('admin:account-deposit', args=[obj.pk]),
            # reverse('admin:account-withdraw', args=[obj.pk]),
        )

    account_actions.short_description = 'Account Actions'
    account_actions.allow_tags = True

admin.site.register(CustomUser, UserAdmin)
admin.site.register(Profile)
