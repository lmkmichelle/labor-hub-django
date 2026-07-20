# Labor Hub

Django 5.2 web app: server-rendered templates + Tailwind CSS v4 + HTMX/Flowbite.
The database is **MySQL** (matching Cornell Media3 hosting); **SQLite** works out of
the box for zero-setup local development. Node.js is only used to (re)build the
Tailwind CSS bundle at build time — the compiled `static/src/output.css` is committed,
so it is not required to run the app.

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

# 3. Configure environment (edit values after copying)
copy .env.example .env
#    For a no-database-setup run, set DATABASE_ENGINE=sqlite3 in .env

# 4. (Optional) rebuild Tailwind CSS after editing templates/styles
npm install
npx @tailwindcss/cli -i ./static/src/input.css -o ./static/src/output.css --watch

# 5. Apply migrations and start the server
py manage.py migrate
py manage.py runserver
```

For a local **MySQL** run, set in `.env`: `DATABASE_ENGINE=mysql`,
`DATABASE_HOST=127.0.0.1`, `DATABASE_PORT=3306`, and the `DATABASE_*` credentials,
then create the database in MySQL before running migrations.

## Run with Docker

```
npm install
npx @tailwindcss/cli -i ./static/src/input.css -o ./static/src/output.css --watch
docker compose up --build
```

Docker Compose runs MySQL 8 as the `db` service (see `docker-compose.yml` and `.env.example`).

### Applying migrations (Docker)

```
docker exec -it nole-app python manage.py makemigrations
docker exec -it nole-app python manage.py migrate
```

### Create a new app

```
docker exec -it nole-app python manage.py startapp <app_name>
```