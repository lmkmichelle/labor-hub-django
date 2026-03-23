from django.db import models
from django.urls import reverse
from accounts.models import CustomUser

# Create your models here.

class Job(models.Model):
    title = models.CharField(max_length=255)
    uploader = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    description = models.TextField()
    url = models.URLField()
    deadline = models.DateField()

    def get_absolute_url(self):
        return reverse('job-detail', kwargs={'pk': self.pk})

    def __str__(self):
        return self.title