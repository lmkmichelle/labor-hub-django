from django.db import models
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

    def __str__(self):
        return self.title