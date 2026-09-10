from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import JSONField

from accounts.models import CustomUser
from core.constants import PAPER_COUNTRY_CHOICES
from core.models import Approvable

User = get_user_model()

class Author(models.Model):
    user = models.ForeignKey(CustomUser, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.user.get_full_name() if self.user else self.name

    class Meta:
        unique_together = [('user', 'name')]

class Publication(Approvable):
    title = models.CharField(max_length=200)
    authors = models.ManyToManyField(Author, related_name='publications')
    abstract = models.TextField()
    country_code = models.CharField(
        max_length=16,
        choices=PAPER_COUNTRY_CHOICES,
        blank=True,
        null=True
    )
    # A flat list of research topics, each an exact RECOMMENDED_KEYWORDS value.
    # Written only through publications.utils.handle_keywords.
    topic = JSONField(default=list, blank=True)
    is_job_market = models.BooleanField(default=False)
    pdf = models.FileField(upload_to='publications/pdf', null=True, blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def formatted_date(self):
        """The paper's public date is when it was submitted."""
        return f"{self.applied_at:%Y-%m-%d}"

