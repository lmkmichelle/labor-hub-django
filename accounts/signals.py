import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .models import Profile, CustomUser, UserApplication

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CustomUser)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(
            user=instance,
            position='',
            department='',
            country_code='',
            website='',
            biography='',
            research_interests=[]
        )

@receiver(post_save, sender=CustomUser)
def save_profile(sender, instance, **kwargs):
    # Only save if profile exists
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(post_save, sender=Profile)
def sync_to_campaign_monitor(sender, instance, **kwargs):
    """Queue a CM list update when preferences or account state changed."""
    from .cm_sync import queue_sync
    queue_sync(instance)


@receiver(pre_delete, sender=CustomUser)
def clean_up_deleted_user(sender, instance, **kwargs):
    """Everything personal that a plain row delete would leave behind.

    Runs for self-service deletion and for a delete in the admin alike:
    papers keep their byline as plain text, uploaded files leave storage,
    the member's applications go, and the address leaves Campaign Monitor.
    Storage and CM work happens after commit and never blocks the delete.
    """
    from publications.models import Author

    full_name = instance.get_full_name()
    Author.objects.filter(user=instance).update(name=full_name)

    files = []
    profile = getattr(instance, "profile", None)
    if profile is not None:
        files += [f for f in (profile.avatar, profile.cv_file) if f]
    applications = UserApplication.objects.filter(email__iexact=instance.email)
    for application in applications:
        if application.resume:
            files.append(application.resume)
        files += [sample.paper for sample in application.research_papers.all() if sample.paper]
    applications.delete()

    email = instance.email

    def after_commit():
        for fieldfile in files:
            try:
                fieldfile.storage.delete(fieldfile.name)
            except Exception:
                logger.exception("Could not delete %s of a deleted account", fieldfile.name)
        from .cm_sync import remove_subscriber
        remove_subscriber(email)

    transaction.on_commit(after_commit)
