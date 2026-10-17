"""Merging duplicate University rows.

The Hipolabs feed keys each institution on its web domain, so a school listed
under two domains arrived as two rows. ``SAME_SCHOOL`` names the pairs that are
really one institution (the keep/drop sides are external ids, which are the
same on every database -- primary keys are not). Different schools that merely
share a name (the many "Glendale Community College"s) are NOT touched; the
picker tells them apart by domain instead.
"""
from django.db import transaction

# (name, country, external_id to keep, external_id to drop)
SAME_SCHOOL = [
    ('University of Bath', 'GB', 'bath.ac.uk', 'bath.edu'),
    ('Keio University', 'JP', 'keio.ac.jp', 'a2.keio.jp'),
    ('Chiba University', 'JP', 'chiba-u.ac.jp', 'chiba-u.jp'),
    ('Ateneo de Manila University', 'PH', 'admu.edu.ph', 'ateneo.edu'),
    ('Cornell College', 'US', 'cornell-iowa.edu', 'cornellcollege.edu'),
    ('Davis & Elkins College', 'US', 'dne.wvnet.edu', 'dewv.edu'),
    ('Thomas Jefferson University', 'US', 'tju.edu', 'jefferson.edu'),
    ('Pondicherry University', 'IN', 'pondiuni.org', 'bicpu.edu.in'),
    ('Regent University College of Science and Technology', 'GH',
     'regent.edu.gh', 'regentghana.net'),
    ('University of Da Nang', 'VN', 'ud.edu.vn', 'udn.vn'),
]

# Rows the importer must not bring back.
DROPPED_EXTERNAL_IDS = frozenset(drop for *_, drop in SAME_SCHOOL)

# Upstream labels the Shenzhen campus with the Hong Kong university's name.
NAME_OVERRIDES = {
    'cuhk.edu.cn': 'The Chinese University of Hong Kong, Shenzhen',
}

# Hand-typed or seeded rows that duplicate a real institution:
# (source, name, country, name of the row to merge into)
STRAY_ROWS = [
    ('write-in', 'Yale', 'US', 'Yale University'),
    ('demo', 'Cornell University', 'US', 'Cornell University'),
]


@transaction.atomic
def merge_universities(keep, drop, *, University, Profile, UserApplication, Seminar):
    """Point everything that referenced ``drop`` at ``keep``, then delete ``drop``."""
    Profile.objects.filter(university=drop).update(university=keep)
    UserApplication.objects.filter(university=drop).update(university=keep)
    Seminar.objects.filter(university=drop).update(university=keep)

    # Alert pills store university ids in a JSON list (ints, or strings from forms).
    for profile in Profile.objects.all().iterator():
        ids = [str(i) for i in profile.alert_universities or []]
        if str(drop.pk) not in ids:
            continue
        merged = []
        for value in ids:
            value = str(keep.pk) if value == str(drop.pk) else value
            if value not in merged:
                merged.append(value)
        profile.alert_universities = [int(v) if v.isdigit() else v for v in merged]
        profile.save(update_fields=['alert_universities'])

    drop.delete()


def merge_known_duplicates(*, University, Profile, UserApplication, Seminar):
    """Apply SAME_SCHOOL, NAME_OVERRIDES and STRAY_ROWS. Safe to run repeatedly.
    Returns how many rows were merged away."""
    models = dict(University=University, Profile=Profile,
                  UserApplication=UserApplication, Seminar=Seminar)
    merged = 0
    for name, country, keep_id, drop_id in SAME_SCHOOL:
        keep = University.objects.filter(
            name=name, country_code=country, external_id=keep_id).first()
        drop = University.objects.filter(
            name=name, country_code=country, external_id=drop_id).first()
        if keep and drop:
            merge_universities(keep, drop, **models)
            merged += 1

    for source, name, country, target_name in STRAY_ROWS:
        stray = University.objects.filter(
            source=source, name=name, country_code=country).first()
        target = University.objects.filter(
            name=target_name, country_code=country).exclude(source=source).first()
        if stray and target:
            merge_universities(target, stray, **models)
            merged += 1

    for external_id, name in NAME_OVERRIDES.items():
        University.objects.filter(external_id=external_id).update(name=name)
    return merged
