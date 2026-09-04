from django.db import models
from django.urls import reverse
from django.utils import timezone
from accounts.models import CustomUser
from core.constants import COUNTRY_CHOICES
from core.models import Approvable


COUNTRY_MAP = dict(COUNTRY_CHOICES)

RANK_CHOICES = [
    ('predoc', 'Predoc'),
    ('postdoc', 'Postdoc'),
    ('assistant_professor', 'Assistant Professor'),
    ('associate_professor', 'Associate Professor'),
    ('full_professor', 'Full Professor'),
    ('other', 'Other'),
]

RANK_MAP = dict(RANK_CHOICES)

# Ranks treated as "junior" for the nav's student/junior jobs filter.
JUNIOR_RANKS = ['predoc', 'postdoc']


class Job(Approvable):
    title = models.CharField(max_length=255)
    employer = models.CharField(
        max_length=255,
        blank=True,
        help_text='Hiring institution or organization',
    )
    pay = models.CharField(
        max_length=255,
        blank=True,
        help_text='e.g. "$70,000–85,000 / year" or "Competitive". Optional.',
    )
    uploader = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    description = models.TextField()
    countries = models.JSONField(default=list, blank=True)
    categories = models.JSONField(default=list, blank=True)
    url = models.URLField()
    deadline = models.DateField()
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['-created_at']

    def get_absolute_url(self):
        return reverse('job-detail', kwargs={'pk': self.pk})

    def country_labels(self):
        labels = []
        for code in self.countries or []:
            labels.append(COUNTRY_MAP.get(code, code))
        return labels

    def category_labels(self):
        labels = []
        for code in self.categories or []:
            labels.append(RANK_MAP.get(code, code))
        return labels

    def __str__(self):
        return self.title
