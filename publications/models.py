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
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

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
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    applied_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    admin_notes = models.TextField(blank=True, help_text="Internal notes for administrators")

    def approve(self, admin_user):
        if self.status != 'pending':
            raise ValueError("Only pending publications can be approved")  # Fix the error message

        self.status = 'approved'
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save()

    def reject(self, admin_user):
        if self.status != 'pending':
            raise ValueError("Only pending publications can be rejected")  # Fix the error message

        self.status = 'rejected'
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save()

    def __str__(self):
        return self.title

    def formatted_date(self):
        return f"{self.date}"
