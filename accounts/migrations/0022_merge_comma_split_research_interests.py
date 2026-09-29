"""Data repair for a bug in the Research Interests Tagify field: with the
default "," delimiter, typing or pasting "Structural models of health,
retirement, and savings" (the one RECOMMENDED_KEYWORDS entry that itself
contains commas -- see core/constants.py) silently split into three separate
pills/list entries instead of one. static/js/tagify.js now sets
delimiters: null to stop it happening again; this migration merges the
already-saved fragments back into the intended single entry.

The list of comma-containing keywords is fixed here (not imported from
core.constants, which can change after this migration is written) to the one
entry affected at the time of writing.
"""
from django.db import migrations

COMMA_KEYWORDS = [
    "Structural models of health, retirement, and savings",
]


def merge_split_fragments(values):
    """Replace, in ``values``, any consecutive run of strings that -- joined
    with ", " -- reconstructs a COMMA_KEYWORDS entry, with that entry.
    Leaves an already-correct list untouched."""
    if not values:
        return values, False
    result = list(values)
    changed = False
    for keyword in COMMA_KEYWORDS:
        parts = keyword.split(", ")
        if len(parts) < 2:
            continue
        i = 0
        while i <= len(result) - len(parts):
            if result[i:i + len(parts)] == parts:
                result[i:i + len(parts)] = [keyword]
                changed = True
            else:
                i += 1
    return result, changed


def merge_research_interests(apps, schema_editor):
    Profile = apps.get_model('accounts', 'Profile')
    for profile in Profile.objects.all():
        merged, changed = merge_split_fragments(profile.research_interests or [])
        if changed:
            profile.research_interests = merged
            profile.save(update_fields=['research_interests'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0021_userapplication_other_networks'),
    ]

    operations = [
        migrations.RunPython(merge_research_interests, migrations.RunPython.noop),
    ]
