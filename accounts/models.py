from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
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
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = str(self.email)

        super().save(*args, **kwargs)


class Profile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars', default='avatars/default.png', blank=True)
    position = models.CharField(max_length=100)
    education = models.CharField(max_length=100)
    country_code = models.CharField(
        max_length=2,
        choices=COUNTRY_CHOICES,
        blank=True,
        null=True
    )
    website = models.URLField(blank=True)
    biography = models.TextField(blank=True)
    research_interests = JSONField(default=list, blank=True)

    def __str__(self):
        return self.user.email

class UserApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    email = models.EmailField()
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    position = models.CharField(max_length=100)
    education = models.CharField(max_length=100)
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
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
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

    def approve(self, admin_user=None):
        if self.status != 'pending':
            raise ValueError("Only pending applications can be approved")

        if CustomUser.objects.filter(email=self.email).exists():
            raise ValueError("A user with this email already exists")

        user = CustomUser.objects.create(
            email=self.email,
            first_name=self.first_name,
            last_name=self.last_name,
            is_active=True
        )

        user.password = self.password
        user.save()

        user.profile.country_code = self.country_code
        user.profile.position = self.position
        user.profile.education = self.education
        user.profile.save()

        self.status = 'approved'
        self.reviewed_at = timezone.now()

        if admin_user:
            self.reviewed_by = admin_user

        self.save()

        return user

    def reject(self, admin_user):
        if self.status != 'pending':
            raise ValueError("Only pending applications can be rejected")

        self.status = 'rejected'
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save()
