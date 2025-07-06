from django.contrib import admin
from django import forms
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.forms import SplitArrayField

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
    list_display = ['title', 'month', 'year', 'country', 'is_job_market']
    search_fields = ['title', 'abstract']

admin.site.register(Publication, PublicationAdmin)
admin.site.register(Author, AuthorAdmin)
