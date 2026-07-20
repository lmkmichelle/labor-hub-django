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