from django.conf import settings
from django.db import models
from django.utils import timezone

from core.constants import COUNTRY_CHOICES


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
    is_example = models.BooleanField(
        default=False,
        help_text=(
            "Illustrative content seeded for testing, not a real submission. "
            "Shown publicly with an 'Example' badge and removable in one step "
            "via `manage.py seed_examples --remove`."
        ),
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


class City(models.Model):
    """A city from the GeoNames ``cities15000`` dataset (population >= 15,000).

    Reference data imported by ``manage.py import_cities`` and used only to
    suggest options for a free-text city field (see ``Event.city``) -- it is
    a suggestion source, not a foreign-key constraint, so a venue in a town
    too small to appear here is still a valid entry.
    """

    geoname_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=200)
    country_code = models.CharField(max_length=2, choices=COUNTRY_CHOICES)
    admin1_name = models.CharField(
        max_length=200, blank=True, default='',
        help_text="State/province/region, e.g. 'New York'.",
    )
    # GeoNames' own admin1 key (e.g. "NY" under country "US"), NOT a reliable
    # ISO 3166-2 code -- e.g. GeoNames' "11" for the Île-de-France region
    # under FR is not that region's ISO code "FR-IDF". Kept only to
    # reconstruct admin1_name from a re-import; never treat it as ISO.
    admin1_code = models.CharField(max_length=20, blank=True, default='')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    population = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-population', 'name']
        indexes = [
            models.Index(fields=['country_code', 'name']),
            # Country-agnostic prefix/infix search for the city-first picker
            # (core.views.city_search) -- the index above can't serve a query
            # that doesn't filter by country_code first.
            models.Index(fields=['name']),
            # Bounding-box prefilter for a future "sort by distance" feature;
            # see the plan's architecture note on nearest-city sorting.
            models.Index(fields=['latitude', 'longitude']),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        if self.admin1_name:
            return f"{self.name}, {self.admin1_name}"
        return self.name


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


class EmailCampaign(models.Model):
    """A newsletter/alerts mailing sent as a Campaign Monitor campaign.

    Campaign Monitor fetches a campaign's HTML from a public URL, so the rendered
    snapshot is stored here and served unguessably at ``email/campaign/<token>``.
    Alerts are *prepared* (segments created) an hour before they are *sent*, since
    CM needs time to calculate new segments. The row also makes sending
    idempotent: a ``sent`` campaign is never sent twice.
    """

    class Kind(models.TextChoices):
        ALERTS = 'alerts', 'Weekly alerts'
        NEWSLETTER = 'newsletter', 'Weekly newsletter'
        NEWSLETTER_MONTHLY = 'newsletter_monthly', 'Monthly newsletter'

    class Status(models.TextChoices):
        PREPARED = 'prepared', 'Prepared'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    kind = models.CharField(max_length=20, choices=Kind.choices)
    token = models.CharField(max_length=64, unique=True, editable=False)
    subject = models.CharField(max_length=200)
    html = models.TextField()
    text = models.TextField()
    # The look-back window the content covers, so the next run continues from it.
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    cm_campaign_id = models.CharField(max_length=64, blank=True)
    segment_ids = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PREPARED)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_kind_display()} {self.created_at:%Y-%m-%d} ({self.status})"


class CampaignMonitorResource(models.Model):
    """The Campaign Monitor id of something this site created there (a list).

    Filled by ``cm_setup`` so nobody copies ids into environment variables; see
    core.cm_lists.
    """
    key = models.CharField(max_length=40, unique=True)
    cm_id = models.CharField(max_length=64)

    def __str__(self):
        return f"{self.key}: {self.cm_id}"


class NewsletterSchedule(models.Model):
    """Admin control over one recurring newsletter (weekly or monthly).

    While ``paused`` the Friday cron skips that newsletter; admins can still send
    it by hand from the Newsletters page in the admin. Rows are created on demand.
    """

    class Kind(models.TextChoices):
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'

    kind = models.CharField(max_length=10, choices=Kind.choices, unique=True)
    paused = models.BooleanField(default=False)
    paused_at = models.DateTimeField(null=True, blank=True)
    paused_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'newsletter'
        verbose_name_plural = 'newsletters'

    @classmethod
    def for_kind(cls, kind):
        return cls.objects.get_or_create(kind=kind)[0]

    def set_paused(self, paused, user=None):
        self.paused = paused
        self.paused_at = timezone.now() if paused else None
        self.paused_by = user if paused else None
        self.save()

    def __str__(self):
        return f"{self.get_kind_display()} newsletter ({'paused' if self.paused else 'active'})"
