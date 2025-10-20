from django.contrib import admin

from seminars.models import Seminar


# Register your models here.

class SeminarAdmin(admin.ModelAdmin):
    list_display = ['title', 'host', 'date', 'location', 'description']
    search_fields = ['title', 'host', 'date', 'location', 'description']

    fieldsets = (
        ('Seminar Information', {
            'fields': ('title', 'host', 'date', 'location', 'description')
        }),
    )

admin.site.register(Seminar, SeminarAdmin)
