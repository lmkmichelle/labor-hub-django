#!/usr/bin/env bash
# Render the weekly and monthly newsletter HTML from a copy of PRODUCTION data.
# Read-only on production; sends nothing; Campaign Monitor is switched off.
#
#   scripts/preview_newsletter.sh [OUT_DIR]     (default: ./newsletter-preview)
#
# Needs the Upsun CLI, logged in. Only the tables the newsletter reads are copied,
# member emails and passwords are replaced, and the copy is deleted when done.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="$(mkdir -p "${1:-newsletter-preview}" && cd "${1:-newsletter-preview}" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "Copying data from production (read-only)..."
upsun ssh -p zv7ifts4uu3lk -e main -A laborhub \
  'python manage.py dumpdata accounts.customuser events jobs special_issues publications core.emailcampaign' \
  > "$WORK/prod.json"

python3 - "$WORK/prod.json" <<'PY'
import json, sys
path = sys.argv[1]
rows = json.load(open(path))
keep = ("first_name", "last_name", "role", "is_active")
for r in rows:
    if r["model"] == "accounts.customuser":
        f = r["fields"]
        r["fields"] = {k: f[k] for k in keep if k in f}
        fake = f"user{r['pk']}@example.invalid"
        r["fields"].update(email=fake, username=fake, password="!")
json.dump(rows, open(path, "w"))
PY

cat > "$WORK/preview_settings.py" <<PY
from nole.settings import *
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "$WORK/preview.sqlite3"}}
CM_API_KEY = ""
PY
export PYTHONPATH="$WORK" DJANGO_SETTINGS_MODULE=preview_settings DATABASE_ENGINE=sqlite3
PY=.venv/bin/python

echo "Loading into a throwaway local database..."
$PY manage.py migrate -v0
$PY manage.py loaddata "$WORK/prod.json" -v0

echo "Rendering..."
OUT="$OUT" $PY manage.py shell -c "
import os
from core.newsletter import newsletter_context, render_newsletter
for kind in ('weekly', 'monthly'):
    ctx = newsletter_context(kind)
    html, text = render_newsletter(ctx)
    open(os.path.join(os.environ['OUT'], f'newsletter-{kind}.html'), 'w').write(html)
    print(kind, {k: len(ctx[k]) for k in ('new_events', 'due_events', 'new_jobs', 'due_jobs',
          'new_special_issues', 'due_special_issues', 'papers', 'job_market_papers')})
"
echo "Done: $OUT/newsletter-weekly.html and newsletter-monthly.html"
