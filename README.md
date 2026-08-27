# Labor Hub

Django 5.2 web app: server-rendered templates + Tailwind CSS v4 + Flowbite.
The database is **MySQL** (matching Cornell Media3 hosting); **SQLite** works out of
the box for zero-setup local development. Node.js is only used to (re)build the
Tailwind CSS bundle at build time — the compiled `static/src/output.css` is committed,
so it is not required to run the app. Flowbite's JavaScript is likewise vendored as a
committed static asset (`static/js/flowbite.min.js`, loaded via `{% static %}`).
One exception remains: **Tagify** (the pill/tag inputs) is still loaded from an
unpinned `cdn.jsdelivr.net` URL in the form and filter templates. Vendoring it
alongside Flowbite is tracked as follow-up work.

> **Styling convention.** Forms render through the shared field partials/tags
> (`{% render_field %}` / `{% render_select %}`); shared list/pagination/empty-state
> structure lives in `templates/partials/`; and repeated controls (buttons, inputs,
> selects, nav links) are defined once as `@apply` component classes in
> `static/src/input.css` — not as duplicated utility strings or inline styles. The app no
> longer uses `django-crispy-forms`, Bootstrap, or HTMX. See
> [`.specify/memory/constitution.md`](.specify/memory/constitution.md) (Principle III).

## Prerequisites

- Python 3.12+ (`python3` on macOS/Linux; the `py` launcher on Windows)
- MySQL 8 (optional locally — SQLite is the default)
- Node.js (optional — only to rebuild Tailwind CSS)

## Run without Docker (local dev)

### macOS / Linux

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure environment  <-- do not skip this
cp .env.example .env
#    Defaults to SQLite (no database setup needed) and DEBUG=1. For local MySQL
#    instead, set DATABASE_ENGINE=mysql and DATABASE_HOST=127.0.0.1 in .env.

# 4. Apply migrations and start the server
python manage.py migrate
python manage.py runserver
```

Then open <http://localhost:8000/>.

### Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py runserver
```

### Rebuilding the CSS (optional)

Only needed after editing templates or `static/src/input.css`; the compiled
bundle is committed, so a plain checkout runs without Node.

```
npm install
npm run watch          # or `npm run build` for a one-off minified build
```

### Step 3 is not optional

Without a `.env`, the app falls back to **production** defaults — `DEBUG=0`,
which turns on the HTTPS redirect, offline asset compression and secure-only
cookies, and leaves `DJANGO_SECRET_KEY` unset. A local run then fails, and the
first error is usually the confusing one below rather than anything about the
missing file:

```
django.core.exceptions.DisallowedHost: Invalid HTTP_HOST header: 'localhost:8000'.
You may need to add 'localhost' to ALLOWED_HOSTS.
```

`cp .env.example .env` fixes it. (`ALLOWED_HOSTS` now defaults to
`localhost,127.0.0.1,[::1]`, so that particular error should not recur, but the
rest of the production defaults still apply until `.env` exists.)

For a local **MySQL** run, set in `.env`: `DATABASE_ENGINE=mysql`,
`DATABASE_HOST=127.0.0.1`, `DATABASE_PORT=3306`, and the `DATABASE_*` credentials,
then create the database in MySQL before running migrations.

### Giving yourself an account

There is no public sign-up for administrators — membership normally goes through
the application-and-approval flow, which needs an approver to already exist. To
create the first one (or to onboard faculty directly):

```
python manage.py create_staff_user "Ada Lovelace <ada@example.edu>" --superuser --country US
```

It prints a generated temporary password once. Sign in at
<http://localhost:8000/accounts/login/> and change it at
`/accounts/password-change/`. Re-running skips accounts that already exist;
`--reset-existing` issues a new password instead.

Superusers get an **Admin guides** entry in the menu under their name
(<http://localhost:8000/help/>) documenting how to approve applicants and review
submitted papers, events, jobs and visits.

### Demo data

To populate the database with realistic demo content (users, profiles, publications,
events, universities, visits, and jobs) for manual UI testing, run:

```
python manage.py seed_demo            # create or refresh demo data
python manage.py seed_demo --reset    # delete demo data first, then re-create it
```

The command is **idempotent** (safe to run repeatedly and on any machine — it never
creates duplicates) and computes all dates relative to today, so upcoming events,
visits, and job deadlines stay in the future. Every demo user shares the password
`demo12345`; e.g. log in as `admin@laborhub.demo` (admin) or
`rosa.researcher@laborhub.demo` (researcher). As a safety guard it **refuses to run
when `DEBUG=False`** (pass `--force` to override), so it can never seed fake data into
the Cornell Media3 production database. All demo accounts use the `@laborhub.demo`
e-mail domain, and `--reset` removes only the data this command created.

### Example content (safe on the live site)

`seed_demo` above is **local-only** — it creates fake users, including a superuser
with a shared password, and refuses to run when `DEBUG=False`. For putting one
worked example in each section of the *real* site during testing, use
`seed_examples` instead:

```
python manage.py seed_examples            # one job, paper, visit and workshop
python manage.py seed_examples --remove   # delete them again
```

It creates no accounts, leaves ownership unset so nothing appears on a real
member's profile, and flags every row it writes so each one renders with a
visible **Example** badge and `--remove` can undo it exactly. Pass
`--owner someone@example.edu` to attribute the examples to a member instead.

## Run with Docker

```
docker compose up --build
```

Docker Compose runs MySQL 8 as the `db` service (see `docker-compose.yml` and `.env.example`).
The app container always connects to this bundled MySQL — Compose sets `DATABASE_ENGINE=mysql`
and `DATABASE_HOST=db` itself, regardless of the `DATABASE_ENGINE` in your `.env` (so the same
`.env` can default to SQLite for native local runs). The `Dockerfile` compiles the Tailwind CSS
bundle in its Node build stage, so no host-side `npm` step is required.

### Applying migrations (Docker)

```
docker exec -it nole-app python manage.py makemigrations
docker exec -it nole-app python manage.py migrate
```

### Create a new app

```
docker exec -it nole-app python manage.py startapp <app_name>
```

## Testing

Tests use Django's built-in test runner (`unittest`-style `TestCase`) with a dedicated
settings module, `nole.settings_test`, so runs are deterministic and do **not** depend on
a committed `.env`. It uses an in-memory SQLite database, disables `django-compressor`
offline compression and HTTPS redirects, and provides a fixed secret key.

```
# Run the whole suite (fast, in-memory SQLite)
python manage.py test --settings=nole.settings_test

# Run a single app or test module
python manage.py test accounts --settings=nole.settings_test
python manage.py test accounts.tests.test_models --settings=nole.settings_test
```

### Coverage

`coverage` is declared in `requirements-dev.txt`; its configuration lives in
`pyproject.toml` (`[tool.coverage.*]`).

```
pip install -r requirements-dev.txt
coverage run manage.py test --settings=nole.settings_test
coverage report          # or: coverage html  -> htmlcov/index.html
```

Each app owns a `tests/` package (`test_models.py`, `test_forms.py`, `test_views.py`,
etc.) covering models, forms, views, utilities, signals, and template tags.

### Browser end-to-end tests (Playwright)

A small, opt-in browser smoke suite lives in `e2e/`. It drives a real Chromium
browser (via `StaticLiveServerTestCase`) through the critical, JavaScript-heavy
flows the test-client tests can't reach: the home page, the login flow, the
contact form, the submit-a-paper page, and the interactive world map. The suite
**skips itself by default** (so the normal test run needs no browser) and only
runs when `RUN_E2E=1` and Playwright's browser are installed:

```
pip install -r requirements-dev.txt
python -m playwright install chromium
RUN_E2E=1 python manage.py test e2e --settings=nole.settings_test
```

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request with four jobs:

- **Lint** — `djlint templates --lint`.
- **Tests (SQLite)** — a Python 3.12 / 3.13 matrix that runs `makemigrations --check`,
  `manage.py check`, and the suite under `coverage` using `nole.settings_test`.
- **Tests (MySQL 8)** — a production-parity job against a MySQL 8 service
  (`DATABASE_ENGINE=mysql`) to catch backend-specific issues before Media3.
- **Browser E2E (Playwright)** — installs Chromium and runs the opt-in `e2e/`
  smoke suite with `RUN_E2E=1`.

## Production (Cornell Media3)

Media3 is a managed Linux VM (Apache + managed MySQL + system Python), **not** a
container host, so production runs natively — not under Docker. The app is served by
**gunicorn** behind **Apache** (reverse proxy + TLS), and Apache serves `/static/`
and `/media/` directly from disk.

Deployment artifacts and a step-by-step runbook live in [`deploy/`](deploy/README.md):

- `deploy/gunicorn.conf.py` / `deploy/gunicorn.service` — gunicorn config + systemd unit
- `deploy/apache/laborhub.conf` — Apache reverse-proxy vhost (static/media aliases + SSL)
- `deploy/README.md` — full Media3 deployment checklist

Production behaviour is driven entirely by environment variables (`DEBUG=0`, a real
`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and the MySQL
`DATABASE_*` values); see `.env.example`.