# Labor Hub

Django 5.2 web app: server-rendered templates + Tailwind CSS v4 + Flowbite.
The database is **MySQL** (matching Cornell Media3 hosting); **SQLite** works out of
the box for zero-setup local development. Node.js is only used to (re)build the
Tailwind CSS bundle at build time — the compiled `static/src/output.css` is committed,
so it is not required to run the app. Flowbite's JavaScript is likewise vendored as a
committed static asset (`static/js/flowbite.min.js`, loaded via `{% static %}`), so the
app pulls **no runtime assets from a CDN**.

> **Styling convention.** Forms render through the shared field partials/tags
> (`{% render_field %}` / `{% render_select %}`); shared list/pagination/empty-state
> structure lives in `templates/partials/`; and repeated controls (buttons, inputs,
> selects, nav links) are defined once as `@apply` component classes in
> `static/src/input.css` — not as duplicated utility strings or inline styles. The app no
> longer uses `django-crispy-forms`, Bootstrap, or HTMX. See
> [`.specify/memory/constitution.md`](.specify/memory/constitution.md) (Principle III).

## Prerequisites

- Python 3.12+ (use the `py` launcher on Windows)
- MySQL 8 (optional locally — SQLite is the default)
- Node.js (optional — only to rebuild Tailwind CSS)

## Run without Docker (local dev)

```powershell
# 1. Create and activate a virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env
#    Defaults to SQLite (no database setup needed). For local MySQL instead, set
#    DATABASE_ENGINE=mysql and DATABASE_HOST=127.0.0.1 in .env.

# 4. (Optional) rebuild Tailwind CSS after editing templates/styles
npm install
npm run watch          # or `npm run build` for a one-off minified build

# 5. Apply migrations and start the server
py manage.py migrate
py manage.py runserver
```

For a local **MySQL** run, set in `.env`: `DATABASE_ENGINE=mysql`,
`DATABASE_HOST=127.0.0.1`, `DATABASE_PORT=3306`, and the `DATABASE_*` credentials,
then create the database in MySQL before running migrations.

### Demo data

To populate the database with realistic demo content (users, profiles, publications,
events, universities, visits, and jobs) for manual UI testing, run:

```
py manage.py seed_demo            # create or refresh demo data
py manage.py seed_demo --reset    # delete demo data first, then re-create it
```

The command is **idempotent** (safe to run repeatedly and on any machine — it never
creates duplicates) and computes all dates relative to today, so upcoming events,
visits, and job deadlines stay in the future. Every demo user shares the password
`demo12345`; e.g. log in as `admin@laborhub.demo` (admin) or
`rosa.researcher@laborhub.demo` (researcher). As a safety guard it **refuses to run
when `DEBUG=False`** (pass `--force` to override), so it can never seed fake data into
the Cornell Media3 production database. All demo accounts use the `@laborhub.demo`
e-mail domain, and `--reset` removes only the data this command created.

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
py manage.py test --settings=nole.settings_test

# Run a single app or test module
py manage.py test accounts --settings=nole.settings_test
py manage.py test accounts.tests.test_models --settings=nole.settings_test
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

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request with three jobs:

- **Lint** — `djlint templates --lint`.
- **Tests (SQLite)** — a Python 3.12 / 3.13 matrix that runs `makemigrations --check`,
  `manage.py check`, and the suite under `coverage` using `nole.settings_test`.
- **Tests (MySQL 8)** — a production-parity job against a MySQL 8 service
  (`DATABASE_ENGINE=mysql`) to catch backend-specific issues before Media3.

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