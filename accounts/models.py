from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import JSONField
from django.utils import timezone

from core.constants import COUNTRY_CHOICES


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('The given email must be set')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('is_active', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if not extra_fields.get('is_staff'):
            raise ValueError('Superuser must have is_staff=True.')
        if not extra_fields.get('is_superuser'):
            raise ValueError('Superuser must have is_superuser=True.')
        if not extra_fields.get('is_active'):
            raise ValueError('Superuser must have is_active=True.')

        return self._create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):

    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        ADMIN = 'admin', 'Admin'
        RESEARCHER = 'researcher', 'Researcher'


    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    date_joined = models.DateTimeField(default=timezone.now)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.RESEARCHER
    )
    advisor = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='advisees',
        limit_choices_to={'role': Role.RESEARCHER},
        help_text="Required for students"
    )
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        if self.role != self.Role.STUDENT:
            self.advisor = None

        if not self.username:
            self.username = str(self.email)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"

    def is_student(self):
        return self.role == self.Role.STUDENT

    def is_researcher(self):
        return self.role == self.Role.RESEARCHER


class Profile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars', blank=True, null=True)
    position = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    # Affiliation. The FK points at the shared University reference table so the
    # field can be picked from a list; university_name is the escape hatch for
    # institutions the table does not know about. Same pair as Seminar uses.
    # Declared as a string so accounts does not import seminars (which already
    # imports accounts) and create a circular import.
    university = models.ForeignKey(
        'seminars.University',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='member_profiles',
    )
    university_name = models.CharField(max_length=255, blank=True)
    country_code = models.CharField(
        max_length=2,
        choices=COUNTRY_CHOICES,
        blank=True,
        null=True
    )

    website = models.URLField(blank=True)
    biography = models.TextField(blank=True)
    research_interests = JSONField(default=list, blank=True)

    # A CV as a link is preferred -- many scholars keep one actively
    # maintained CV online rather than a PDF that goes stale the moment it's
    # uploaded -- but a PDF upload is still supported for anyone who doesn't
    # have one. See cv_link() for which one actually gets shown.
    cv_url = models.URLField(blank=True, help_text="Link to your CV, if you keep one online.")
    cv_file = models.FileField(
        upload_to='cvs/', blank=True, null=True,
        validators=[FileExtensionValidator(['pdf'])],
        help_text="Or upload a CV as a PDF.",
    )

    def cv_link(self):
        """The URL to show/link for this person's CV: the maintained link if
        they set one, else the uploaded PDF, else nothing."""
        if self.cv_url:
            return self.cv_url
        if self.cv_file:
            return self.cv_file.url
        return ""

    class DigestFrequency(models.TextChoices):
        OFF = 'off', 'Off'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'

    digest_frequency = models.CharField(
        max_length=10,
        choices=DigestFrequency.choices,
        default=DigestFrequency.OFF,
        help_text="How often to receive an email digest of newly added content.",
    )
    last_digest_sent_at = models.DateTimeField(null=True, blank=True)

    # Weekly alerts for a specific interest, separate from the general digest
    # above. Alerts are considered "on" whenever either list is non-empty --
    # there's no separate enable flag -- see accounts.alerts.send_user_alerts.
    alert_topics = JSONField(
        default=list, blank=True,
        help_text="Get a weekly email when a new paper on one of these topics is posted.",
    )
    alert_countries = JSONField(
        default=list, blank=True,
        help_text="Get a weekly email when a new visit to one of these countries is posted.",
    )
    # University ids (not names), so a renamed institution keeps matching.
    alert_universities = JSONField(
        default=list, blank=True,
        help_text="Get a weekly email when a new visit to one of these institutions is posted.",
    )
    last_alert_sent_at = models.DateTimeField(null=True, blank=True)
    # Set when the 2-year student deactivation warning is emailed, so it goes
    # out once. See deactivate_expired_students.
    deactivation_warned_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.user.email

    def get_university_display(self):
        """Affiliation for display: the picked university, else the typed name."""
        if self.university:
            return self.university.name
        return self.university_name

    def research_interest_list(self):
        """Return research interests as a flat list of strings.

        Handles both plain strings and the legacy Tagify ``{"value": ...}``
        shape so templates can render them consistently.
        """
        normalized = []
        for interest in self.research_interests or []:
            if isinstance(interest, dict):
                value = interest.get('value', '')
            else:
                value = interest
            value = str(value).strip() if value is not None else ''
            if value:
                normalized.append(value)
        return normalized

class UserApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    email = models.EmailField()
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    role = models.CharField(max_length=255, choices=CustomUser.Role.choices, default=CustomUser.Role.RESEARCHER)
    position = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    university = models.ForeignKey(
        'seminars.University',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applications',
    )
    university_name = models.CharField(max_length=255, blank=True)
    password = models.CharField(max_length=128)
    country_code = models.CharField(
        max_length=2,
        choices=COUNTRY_CHOICES,
        blank=True,
        null=True
    )
    motivation = models.TextField(
        help_text="Why do you want to join this platform?",
        blank=True
    )
    website = models.URLField(blank=True)
    # [{"network": "NBER", "url": "..."}] -- declared networks, admin review
    # only. Never copied to Profile, never shown publicly.
    other_networks = models.JSONField(default=list, blank=True)
    resume = models.FileField(
        help_text="Please upload a copy of your resume. pdf or docx only.", blank=True, null=True
    )
    # Preferred over resume when set -- see Profile.cv_url/cv_link(). Both are
    # carried over to the new member's profile on approve().
    cv_url = models.URLField(
        blank=True, help_text="Link to your CV, if you keep one online (optional).")
    advisor = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"role": CustomUser.Role.RESEARCHER},
        related_name="student_applications",
        help_text="Only required for student applications",
    )
    # Fellow applications only: "I used to have a student account." The number
    # lets approve() attach that student-era job market paper to the new
    # account. Optional -- an applicant may not remember it.
    previous_student_account = models.BooleanField(
        default=False, verbose_name='Previously had a student account')
    previous_jm_paper_number = models.CharField(
        max_length=20, blank=True,
        verbose_name='Job market paper number',
        help_text='Discussion series number of their job market paper, e.g. J3.',
    )
    status = models.CharField(max_length=10, choices=Status.choices, default='pending')
    applied_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_applications'
    )
    admin_notes = models.TextField(blank=True, help_text="Internal notes for administrators")

    class Meta:
        ordering = ['-applied_at']

    def get_university_display(self):
        """Affiliation for display: the picked university, else the typed name."""
        if self.university:
            return self.university.name
        return self.university_name

    def approve(self, admin_user=None, advisor=None):
        if self.status != 'pending':
            raise ValueError("Only pending applications can be approved")

        existing = self.returning_student()
        if CustomUser.objects.filter(email=self.email).exists() and existing is None:
            raise ValueError("A user with this email already exists")

        # Fall back to the advisor the student named on the application. Without
        # this, approving a student through the admin (which passes no advisor)
        # silently drops the advisor link.
        advisor = advisor or self.advisor

        if existing is not None:
            # A former student becoming a fellow keeps their account, so every
            # paper and post stays attached. Their password is left alone: the
            # applicant could be someone else typing a stranger's address, and
            # the email below sends the real owner to the reset link.
            user = existing
            user.is_active = True
            user.role = self.role
            user.advisor = None
            user.first_name = self.first_name
            user.last_name = self.last_name
            user.save()
        else:
            user = CustomUser.objects.create(
                email=self.email,
                password=self.password,
                first_name=self.first_name,
                last_name=self.last_name,
                is_active=True,
                role = self.role,
                advisor = advisor if self.role == CustomUser.Role.STUDENT else None,
            )
            user.save()
        user.profile.position = self.position
        user.profile.department = self.department
        university = self.university
        university_name = self.university_name
        if not university and university_name and self.country_code:
            # Local import: seminars already imports accounts, so importing
            # University at module level here would be circular.
            from seminars.models import University
            promoted = University.from_write_in(university_name, self.country_code)
            if promoted:
                university = promoted
                university_name = ''
        user.profile.university = university
        user.profile.university_name = university_name
        user.profile.country_code = self.country_code
        user.profile.website = self.website
        user.profile.cv_url = self.cv_url
        if self.resume:
            user.profile.cv_file = self.resume
        user.profile.save()

        self.status = self.Status.APPROVED
        self.reviewed_at = timezone.now()

        if admin_user:
            self.reviewed_by = admin_user
        self.save()

        self.claim_note = self._claim_job_market_paper(user) if existing is None else ''

        # Let the new member know their account is live and they can sign in.
        from accounts.emails import send_application_approved_email
        send_application_approved_email(user, returning=existing is not None)

        return user

    def returning_student(self):
        """The inactive student account this fellow application would reactivate,
        or None. Same email, deactivated, still a student."""
        if self.role != CustomUser.Role.RESEARCHER:
            return None
        return CustomUser.objects.filter(
            email=self.email, role=CustomUser.Role.STUDENT, is_active=False).first()

    def _claim_job_market_paper(self, user):
        """Attach the applicant's student-era job market paper to ``user``.

        Only when they said they had a student account and gave a number, and
        only to the author entry matching their name -- so typing someone
        else's paper number attaches nothing. Returns a short note for the
        admin ("" when nothing was claimed, a warning when it didn't attach).
        """
        if not (self.previous_student_account and self.previous_jm_paper_number):
            return ''
        # Local import: publications imports accounts.
        from publications.models import Publication
        paper = Publication.find_original(self.previous_jm_paper_number, job_market_only=True)
        if paper is None:
            return f'Job market paper "{self.previous_jm_paper_number}" was not found.'
        full_name = f"{self.first_name} {self.last_name}".strip().lower()
        for author in paper.authors.select_related('user'):
            label = (author.user.get_full_name() if author.user else author.name) or ''
            if label.strip().lower() == full_name:
                author.user = user
                author.save(update_fields=['user'])
                return f'Job market paper {paper.display_number} was attached to this account.'
        return (f'Job market paper {paper.display_number} has no author named '
                f'"{self.first_name} {self.last_name}", so it was not attached.')

    def reject(self, admin_user):
        if self.status != self.Status.PENDING:
            raise ValueError("Only pending applications can be rejected")

        self.status = self.Status.REJECTED
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save()

        from accounts.emails import send_application_rejected_email
        send_application_rejected_email(self)

class ResearchPaper(models.Model):
    application = models.ForeignKey(
        UserApplication,
        on_delete=models.CASCADE,
        related_name='research_papers'
    )
    paper = models.FileField(
        upload_to='research_papers/',
        help_text="Upload your research paper in PDF format"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(paper__endswith='.pdf'),
                name='paper_is_pdf'
            )
        ]

    def __str__(self):
        return f"Research paper for {self.application.email}"
