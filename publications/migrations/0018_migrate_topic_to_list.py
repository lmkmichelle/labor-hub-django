from django.db import migrations


def topic_to_list(apps, schema_editor):
    Publication = apps.get_model('publications', 'Publication')
    for pub in Publication.objects.exclude(topic='').only('id', 'topic').iterator():
        value = (pub.topic or '').strip()
        pub.topic_tmp = [value] if value else []
        pub.save(update_fields=['topic_tmp'])


def list_to_topic(apps, schema_editor):
    Publication = apps.get_model('publications', 'Publication')
    for pub in Publication.objects.only('id', 'topic_tmp').iterator():
        values = pub.topic_tmp or []
        pub.topic = (values[0] if values else '')[:300]
        pub.save(update_fields=['topic'])


class Migration(migrations.Migration):
    """Step 2 of 3: carry the legacy free-text topic across verbatim. Values are
    NOT filtered against RECOMMENDED_KEYWORDS -- the closed list is enforced
    only on new submissions (PublicationForm.clean_topics_input).
    """

    dependencies = [
        ('publications', '0017_publication_topic_tmp'),
    ]

    operations = [
        migrations.RunPython(topic_to_list, list_to_topic),
    ]
