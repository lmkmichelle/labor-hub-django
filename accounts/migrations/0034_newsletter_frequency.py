"""Digest and newsletter are one thing: rename the setting, make weekly the default
and switch every existing member to it (opt-out)."""
from django.db import migrations, models


def everyone_weekly(apps, schema_editor):
    apps.get_model("accounts", "Profile").objects.update(newsletter_frequency="weekly")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0033_student_reminded_at"),
    ]

    operations = [
        migrations.RenameField(
            model_name="profile", old_name="digest_frequency", new_name="newsletter_frequency"),
        migrations.AlterField(
            model_name="profile",
            name="newsletter_frequency",
            field=models.CharField(
                choices=[("off", "Off"), ("weekly", "Weekly"), ("monthly", "Monthly")],
                default="weekly", max_length=10,
                help_text="How often to receive the Labor Hub newsletter."),
        ),
        migrations.RunPython(everyone_weekly, migrations.RunPython.noop),
        migrations.RemoveField(model_name="profile", name="last_digest_sent_at"),
    ]
