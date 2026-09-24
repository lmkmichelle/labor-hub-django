from django.db import models
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from core.constants import COUNTRY_CHOICES
from core.models import Approvable

_COUNTRY_NAMES = dict(COUNTRY_CHOICES)

class Event(Approvable):
    CATEGORY_CHOICES = [
        ('conference', 'Conference'),
        ('workshop', 'Workshop'),
        ('schools', 'Seasonal Schools'),
        ('courses', 'Courses/Retreats'),
        ('other', 'Other'),
    ]

    # Kept as an alias: EventForm and the list facet both reference it, and the
    # member-visible set is now identical to the full set.
    PUBLIC_CATEGORY_CHOICES = CATEGORY_CHOICES

    title = models.CharField(max_length=255)
    description = models.TextField()
    date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True, help_text='Application deadline for this event')
    application_url = models.URLField(
        blank=True,
        help_text='Link to the application or registration page for this event',
    )
    # location is derived (see save()) from country_code/city/venue for any
    # event created or edited through the structured picker. It stays its own
    # column -- rather than becoming a property -- so admin search/sort and
    # the various card/digest readers that already read event.location keep
    # working unchanged. A pre-picker event's hand-typed location survives
    # untouched until someone fills in the structured fields for it.
    location = models.CharField(max_length=255, blank=True, default='')
    country_code = models.CharField(max_length=2, choices=COUNTRY_CHOICES, blank=True, default='')
    city = models.CharField(max_length=255, blank=True, default='')
    # Filled by static/js/location-picker.js when the city was chosen from a
    # suggestion; left blank for a hand-typed city not in core.models.City.
    # Denormalised onto the event itself (not looked up via a join at sort
    # time) so a future distance sort orders by the row's own coordinates,
    # not a fuzzy match on the free-text city string.
    admin1_name = models.CharField(max_length=200, blank=True, default='')
    admin1_code = models.CharField(max_length=20, blank=True, default='')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    venue = models.CharField(
        max_length=255, blank=True, default='',
        help_text="Optional, e.g. a building or conference center name.",
    )
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

    def get_absolute_url(self):
        return reverse('event-detail', kwargs={'pk': self.pk})

    @property
    def is_upcoming(self):
        return self.date >= timezone.now()

    def save(self, *args, **kwargs):
        if self.city or self.country_code:
            country_name = _COUNTRY_NAMES.get(self.country_code, '')
            self.location = ", ".join(
                part for part in (self.venue, self.city, self.admin1_name, country_name)
                if part
            )
        super().save(*args, **kwargs)
