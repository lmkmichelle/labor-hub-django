from django.contrib.auth import get_user_model
from django.utils import timezone
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

class Publication(models.Model):
    title = models.CharField(max_length=200)
    authors = models.ManyToManyField(Author, related_name='publications')
    date = models.DateField(default=timezone.now)
    abstract = models.TextField()
    country_code = models.CharField(
        max_length=2,
        choices=COUNTRY_CHOICES,
        blank=True,
        null=True
    )
    topic = models.CharField(max_length=300, blank=True)
    keywords = JSONField(default=list)
    study_url = models.URLField()
    is_job_market = models.BooleanField()
    pdf = models.FileField(upload_to='publications/pdf', null=True, blank=True)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    def formatted_date(self):
        return f"{self.date}"
