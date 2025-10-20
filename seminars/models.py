from django.db import models

from accounts.models import CustomUser


class Seminar(models.Model):
    title = models.CharField(max_length=255)
    host = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    date = models.DateTimeField()
    location = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return f"{self.title} by {self.host} on {self.date.strftime('%Y-%m-%d')}"
