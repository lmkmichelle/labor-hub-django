from django.contrib import admin

from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
	list_display = ('title', 'uploader', 'deadline')
	search_fields = ('title', 'description', 'uploader__first_name', 'uploader__last_name', 'uploader__email')
	ordering = ('deadline',)
