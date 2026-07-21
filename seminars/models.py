from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError

from accounts.models import CustomUser
from core.constants import COUNTRY_CHOICES


COUNTRY_MAP = dict(COUNTRY_CHOICES)


class University(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    country_code = models.CharField(max_length=2, choices=COUNTRY_CHOICES, null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    source = models.CharField(max_length=64, null=True, blank=True, default='')
    external_id = models.CharField(max_length=128, null=True, blank=True, default='')

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['source', 'external_id']),
        ]

    def __str__(self):
        if self.country_code:
            return f"{self.name} ({COUNTRY_MAP.get(self.country_code, self.country_code)})"
        return self.name


class Seminar(models.Model):
    posted_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='seminar_announcements'
    )
    visitor_name = models.CharField(max_length=255, null=True, blank=True)
    visitor_email = models.EmailField(null=True, blank=True)
    visitor_affiliation = models.CharField(max_length=255, null=True, blank=True)
    university = models.ForeignKey(
        University,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='seminar_announcements'
    )
    university_name = models.CharField(max_length=255, null=True, blank=True)
    visit_start = models.DateField(null=True, blank=True)
    visit_end = models.DateField(null=True, blank=True)
    countries = models.JSONField(default=list, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_absolute_url(self):
        return reverse('seminar-detail', kwargs={'pk': self.pk})

    def country_labels(self):
        labels = []
        for code in self.countries or []:
            labels.append(COUNTRY_MAP.get(code, code))
        return labels

    def get_university_display(self):
        if self.university:
            return self.university.name
        if self.university_name:
            return self.university_name
        return 'University TBA'

    def clean(self):
        super().clean()
        if self.visit_start and self.visit_end and self.visit_end < self.visit_start:
            raise ValidationError({'visit_end': 'Visit end date cannot be earlier than visit start date.'})
        if not self.university and not (self.university_name or '').strip():
            raise ValidationError({'university_name': 'Provide a university or a custom university name.'})

    def __str__(self):
        return f"{self.visitor_name} visiting {self.get_university_display()} ({self.visit_start})"

