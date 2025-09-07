from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import JSONField

from accounts.models import CustomUser
from core.constants import COUNTRY_CHOICES

User = get_user_model()

class Author(models.Model):
    user = models.ForeignKey(CustomUser, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.user.get_full_name() if self.user else self.name

    class Meta:
        unique_together = [('user', 'name')]

MONTH_CHOICES = [
        ('January', 'January'),
        ('February', 'February'),
        ('March', 'March'),
        ('April', 'April'),
        ('May', 'May'),
        ('June', 'June'),
        ('July', 'July'),
        ('August', 'August'),
        ('September', 'September'),
        ('October', 'October'),
        ('November', 'November'),
        ('December', 'December'),
    ]

class Publication(models.Model):
    title = models.CharField(max_length=200)
    authors = models.ManyToManyField(Author, related_name='publications')
    month = models.CharField(max_length=20, choices=MONTH_CHOICES)
    year = models.PositiveIntegerField()
    abstract = models.TextField()
    country_code = models.CharField(
        max_length=2,
        choices=COUNTRY_CHOICES,
        blank=True,
        null=True
    )
    keywords = JSONField(default=list)
    study_url = models.URLField()
    is_job_market = models.BooleanField()
    pdf = models.FileField(upload_to='publications/pdf', null=True, blank=True)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    def formatted_date(self):
        return f"{self.month} {self.year}"
