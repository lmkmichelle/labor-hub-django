from django.db import migrations


def normalize_research_interests(apps, schema_editor):
    """Convert any Tagify-style [{"value": ...}] interests into plain strings."""
    Profile = apps.get_model('accounts', 'Profile')
    for profile in Profile.objects.all():
        raw_interests = profile.research_interests or []
        normalized = []
        for interest in raw_interests:
            if isinstance(interest, dict):
                value = interest.get('value', '')
            else:
                value = interest
            value = str(value).strip() if value is not None else ''
            if value:
                normalized.append(value)
        if normalized != raw_interests:
            profile.research_interests = normalized
            profile.save(update_fields=['research_interests'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0016_alter_profile_avatar'),
    ]

    operations = [
        migrations.RunPython(normalize_research_interests, migrations.RunPython.noop),
    ]
