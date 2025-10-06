from django.db import models
from django.utils import timezone

from accounts.models import CustomUser

class Event(models.Model):
    CATEGORY_CHOICES = [
        ('conference', 'Conference'),
        ('seminar', 'Seminar'),
        ('workshop', 'Workshop'),
        ('webinar', 'Webinar'),
        ('networking', 'Networking Event'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    host = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hosted_events'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_events'
    )

    class Meta:
        ordering = ['date']

    def __str__(self):
        return self.title

    @property
    def is_upcoming(self):
        return self.date >= timezone.now()
