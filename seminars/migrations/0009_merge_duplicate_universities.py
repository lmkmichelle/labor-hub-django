from django.db import migrations

from seminars.university_merge import merge_known_duplicates


def merge(apps, schema_editor):
    merge_known_duplicates(
        University=apps.get_model('seminars', 'University'),
        Profile=apps.get_model('accounts', 'Profile'),
        UserApplication=apps.get_model('accounts', 'UserApplication'),
        Seminar=apps.get_model('seminars', 'Seminar'),
    )


class Migration(migrations.Migration):
    dependencies = [
        ('seminars', '0008_seminar_visit_type'),
        ('accounts', '0028_profile_cm_sync_state'),
    ]

    operations = [migrations.RunPython(merge, migrations.RunPython.noop)]
