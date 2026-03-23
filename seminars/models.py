from django.db import models
from django.db.models import Q
from django.urls import reverse

from accounts.models import CustomUser
from core.constants import COUNTRY_CHOICES


COUNTRY_MAP = dict(COUNTRY_CHOICES)


class Seminar(models.Model):
    title = models.CharField(max_length=255)
    host = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    date = models.DateTimeField()
    countries = models.JSONField(default=list, blank=True)
    description = models.TextField()

    def get_absolute_url(self):
        return reverse('seminar-detail', kwargs={'pk': self.pk})

    def country_labels(self):
        labels = []
        for code in self.countries or []:
            labels.append(COUNTRY_MAP.get(code, code))
        return labels

    def __str__(self):
        return f"{self.title} by {self.host} on {self.date.strftime('%Y-%m-%d')}"


class SeminarInterest(models.Model):
    seminar = models.ForeignKey(
        Seminar,
        on_delete=models.CASCADE,
        related_name='interests'
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='seminar_interests'
    )
    guest_name = models.CharField(max_length=255, blank=True)
    guest_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['seminar', 'user'],
                condition=Q(user__isnull=False),
                name='unique_seminar_interest_user'
            ),
            models.UniqueConstraint(
                fields=['seminar', 'guest_email'],
                condition=Q(guest_email__gt=''),
                name='unique_seminar_interest_guest_email'
            ),
        ]

    def save(self, *args, **kwargs):
        if self.guest_email:
            self.guest_email = self.guest_email.strip().lower()
        if self.guest_name:
            self.guest_name = self.guest_name.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.user:
            return f"{self.user} interested in {self.seminar}"
        return f"{self.guest_email} interested in {self.seminar}"
