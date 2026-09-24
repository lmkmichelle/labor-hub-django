from django.db import models
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from core.models import Approvable


class SpecialIssue(Approvable):
    """A journal's call for papers for a special issue.

    ``editors`` is an ordered JSON list of ``{"name": str, "user_id": int|None}``
    rather than a many-to-many: order matters (the poster is always first) and
    most co-editors are not Labor Hub members, so they are just names. A
    non-null ``user_id`` links the editor to a member's profile.
    """

    journal = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    description = models.TextField(
        help_text='Include a link to the call for papers.',
    )
    call_url = models.URLField(blank=True)
    submission_deadline = models.DateField()
    posted_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='special_issues',
    )
    editors = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['submission_deadline']

    def __str__(self):
        return f"{self.title} ({self.journal})"

    def get_absolute_url(self):
        return reverse('special-issue-detail', kwargs={'pk': self.pk})

    @property
    def is_open(self):
        return self.submission_deadline >= timezone.localdate()

    def editor_entries(self):
        """Editors in order, each with a ``name`` and ``user_id`` (or None)."""
        return [
            {'name': entry.get('name', ''), 'user_id': entry.get('user_id')}
            for entry in (self.editors or [])
            if entry.get('name')
        ]

    def save(self, *args, **kwargs):
        # Enforced here, not in a view, so the admin and any future entry
        # point get the same guarantee: the poster is always an editor, first.
        if self.posted_by_id:
            entries = [
                e for e in (self.editors or [])
                if e.get('user_id') != self.posted_by_id
            ]
            entries.insert(0, {
                'name': self.posted_by.get_full_name() or self.posted_by.email,
                'user_id': self.posted_by_id,
            })
            self.editors = entries
        super().save(*args, **kwargs)
