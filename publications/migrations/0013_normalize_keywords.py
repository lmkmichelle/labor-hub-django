from django.db import migrations


def normalize_keywords(apps, schema_editor):
    """Convert any Tagify-style [{"value": ...}] keywords into plain strings."""
    Publication = apps.get_model('publications', 'Publication')
    for publication in Publication.objects.all():
        raw_keywords = publication.keywords or []
        normalized = []
        for keyword in raw_keywords:
            if isinstance(keyword, dict):
                value = keyword.get('value', '')
            else:
                value = keyword
            value = str(value).strip() if value is not None else ''
            if value:
                normalized.append(value)
        if normalized != raw_keywords:
            publication.keywords = normalized
            publication.save(update_fields=['keywords'])


class Migration(migrations.Migration):

    dependencies = [
        ('publications', '0012_alter_publication_is_job_market'),
    ]

    operations = [
        migrations.RunPython(normalize_keywords, migrations.RunPython.noop),
    ]
