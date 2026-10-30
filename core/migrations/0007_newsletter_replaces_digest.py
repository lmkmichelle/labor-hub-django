"""The digest and the newsletter are one thing: fold the digest campaign kinds into it."""
from django.db import migrations, models


def fold_digests(apps, schema_editor):
    apps.get_model("core", "EmailCampaign").objects.filter(
        kind__in=["digest_weekly", "digest_monthly"]).update(kind="newsletter")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_newsletter_kind"),
    ]

    operations = [
        migrations.RunPython(fold_digests, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="emailcampaign",
            name="kind",
            field=models.CharField(
                choices=[("alerts", "Weekly alerts"), ("newsletter", "Newsletter")],
                max_length=20),
        ),
        migrations.CreateModel(
            name="CampaignMonitorResource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=40, unique=True)),
                ("cm_id", models.CharField(max_length=64)),
            ],
        ),
    ]
