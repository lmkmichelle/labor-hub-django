from django.db import migrations, models


class Migration(migrations.Migration):
    """Step 1 of 3 converting Publication.topic from a free-text CharField to a
    JSON list. An in-place type change would rebuild the table on SQLite and
    coerce the existing text into invalid JSON, so a new column is added here,
    populated in 0018, and swapped in for the old one in 0019.
    """

    dependencies = [
        ('publications', '0016_alter_publication_country_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='publication',
            name='topic_tmp',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
