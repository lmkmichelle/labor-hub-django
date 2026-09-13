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

    submitted_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_publications',
    )
    jm_advisor = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='advised_job_market_papers',
        limit_choices_to={'role': CustomUser.Role.RESEARCHER},
        verbose_name='Job market advisor',
    )
    # None = not answered, True = acknowledged, False = declined.
    jm_advisor_acknowledged = models.BooleanField(null=True, blank=True)
    jm_advisor_responded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

    def formatted_date(self):
        """The paper's public date is when it was submitted."""
        return f"{self.applied_at:%Y-%m-%d}"

    @property
    def has_advisor_response(self):
        return self.jm_advisor_acknowledged is not None

