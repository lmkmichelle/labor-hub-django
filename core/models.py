from django.conf import settings
from django.db import models
from django.utils import timezone


class ApprovalStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class ApprovableQuerySet(models.QuerySet):
    """QuerySet helpers for models with a moderation workflow."""

    def approved(self):
        return self.filter(status=ApprovalStatus.APPROVED)

    def pending(self):
        return self.filter(status=ApprovalStatus.PENDING)

    def rejected(self):
        return self.filter(status=ApprovalStatus.REJECTED)


class Approvable(models.Model):
    """Abstract base adding a pending/approved/rejected moderation workflow.

    Concrete models (publications, events, visits, jobs) get a ``status`` field
    that defaults to pending, review audit fields, admin notes, and
    ``approve``/``reject`` helpers. Use ``Model.objects.approved()`` to fetch the
    publicly visible rows. Keeping this logic in one place avoids re-implementing
    the same status machinery on every content model.
    """

    status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_%(class)ss',
    )
    admin_notes = models.TextField(
        blank=True, help_text="Internal notes for administrators"
    )

    objects = ApprovableQuerySet.as_manager()

    class Meta:
        abstract = True

    @property
    def is_approved(self):
        return self.status == ApprovalStatus.APPROVED

    def _mark_reviewed(self, status, admin_user):
        self.status = status
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save()

    def approve(self, admin_user=None):
        if self.status != ApprovalStatus.PENDING:
            raise ValueError("Only pending items can be approved")
        self._mark_reviewed(ApprovalStatus.APPROVED, admin_user)

    def reject(self, admin_user=None):
        if self.status != ApprovalStatus.PENDING:
            raise ValueError("Only pending items can be rejected")
        self._mark_reviewed(ApprovalStatus.REJECTED, admin_user)


class ContactMessage(models.Model):
    """A message submitted through the public contact form.

    Submissions are stored so they survive email outages and can be triaged in
    the Django admin; a notification email is also sent when one is created.
    """

    name = models.CharField(max_length=150)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(
        default=False,
        help_text="Mark once this inquiry has been followed up on.",
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} <{self.email}> ({self.created_at:%Y-%m-%d})"
