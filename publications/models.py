from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.conf import settings
from django.utils import timezone

User = get_user_model()

class Author(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.user.get_full_name() if self.user else self.name

    class Meta:
        unique_together = [('user', 'name')]

# Create your models here.
class Publication(models.Model):
    title = models.CharField(max_length=200)
    authors = models.ManyToManyField(Author, related_name='publications')
    year = models.IntegerField()
    abstract = models.TextField()
    country = models.CharField(max_length=200)
    keywords = ArrayField(models.CharField(max_length=200))
    sample_size = models.IntegerField()
    study_url = models.URLField()
    is_job_market = models.BooleanField()

    def __str__(self):
        return self.title
