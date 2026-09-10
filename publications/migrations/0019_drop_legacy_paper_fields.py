from django.db import migrations, models


class Migration(migrations.Migration):
    """Step 3 of 3: drop the retired fields and rename topic_tmp -> topic.

    Per the Sept 2026 review, the paper form no longer collects a study link,
    a manual date (the submission timestamp is used instead), or separate
    keywords. ``study_url`` is first relaxed to blank/default so the reverse
    of this migration can re-add it without tripping the NOT NULL constraint
    on existing rows (the data itself is gone either way).
    """

    dependencies = [
        ('publications', '0018_migrate_topic_to_list'),
    ]

    operations = [
        migrations.AlterField(
            model_name='publication',
            name='study_url',
            field=models.URLField(blank=True, default=''),
        ),
        migrations.RemoveField(model_name='publication', name='study_url'),
        migrations.RemoveField(model_name='publication', name='date'),
        migrations.RemoveField(model_name='publication', name='keywords'),
        migrations.RemoveField(model_name='publication', name='topic'),
        migrations.RenameField(
            model_name='publication', old_name='topic_tmp', new_name='topic',
        ),
    ]
