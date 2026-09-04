from django.db import models
from django.utils import timezone

from accounts.models import CustomUser
from core.models import Approvable

class Event(Approvable):
    CATEGORY_CHOICES = [
        ('conference', 'Conference'),
        ('podcast', 'Live Podcast'),
        ('workshop', 'Workshop'),
        ('schools', 'Seasonal Schools'),
        ('courses', 'Courses/Retreats'),
        ('other', 'Other'),
    ]

    # Categories a member may pick when submitting an event. "Live Podcast" is
    # admin-only, so it is excluded here while staying in CATEGORY_CHOICES for
    # display and for the public list-page filter facet.
    PUBLIC_CATEGORY_CHOICES = [c for c in CATEGORY_CHOICES if c[0] != 'podcast']

    title = models.CharField(max_length=255)
    description = models.TextField()
    date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True, help_text='Application deadline for this event')
    application_url = models.URLField(
        blank=True,
        help_text='Link to the application or registration page for this event',
    )
    location = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    host = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hosted_events'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return self.title

    @property
    def is_upcoming(self):
        return self.date >= timezone.now()
