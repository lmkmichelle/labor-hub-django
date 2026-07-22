# Media3 Deployment (Labor Hub)

Step-by-step runbook for deploying the Django app to a Cornell **Media3** managed
Linux VM. Media3 provides Apache, managed MySQL, and system Python; it is **not** a
container host, so the app runs natively (no Docker).

**Architecture:** `Browser --HTTPS--> Apache (TLS, reverse proxy) --> gunicorn
(127.0.0.1:8000) --> Django --> managed MySQL`. Apache serves `/static/` and `/media/`
directly from disk (not through the Python process).

## 0. Confirm with Media3 before you start
- [ ] Shell/SSH access, and permission to install/run a **systemd** service (or
      supervisor). If only WebDAV / no service control is available, use the
      **mod_wsgi fallback** (bottom of this file) instead of gunicorn.
- [ ] Apache modules `proxy`, `proxy_http`, `headers`, `ssl` enabled, and permission
      to add a vhost.
- [ ] A managed **MySQL** database provisioned; note host, name, user, password.
- [ ] An **SSL certificate** issued for your hostname (Media3-managed); note the cert
      and key paths.
- [ ] Your public **hostname** (e.g. `laborhub.cornell.edu`).

## 1. Get the code and a virtualenv
```bash
sudo mkdir -p /var/www/laborhub && sudo chown "$USER" /var/www/laborhub
git clone <repo-url> /var/www/laborhub
cd /var/www/laborhub
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 2. Create the production .env
```bash
cp .env.example .env
# Generate a secret key:
.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(64))"
```
Edit `.env` and set at minimum:
```
DEBUG=0
DJANGO_SECRET_KEY=<generated key>
DJANGO_ALLOWED_HOSTS=laborhub.cornell.edu
CSRF_TRUSTED_ORIGINS=https://laborhub.cornell.edu
DATABASE_ENGINE=mysql
DATABASE_NAME=<db>
DATABASE_USERNAME=<user>
DATABASE_PASSWORD=<password>
DATABASE_HOST=<media3-mysql-host>
DATABASE_PORT=3306
```
Lock it down: `chmod 600 .env`.

## 3. Migrate and build static assets
```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py compress --force       # offline-compress the CSS bundle
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser         # optional
```
> The Tailwind bundle `static/src/output.css` is committed, so **Node is not required
> on the VM**. If you change styles, rebuild locally (`npm run build`), commit the new
> `output.css`, then re-run `compress` + `collectstatic` on the VM.

## 4. Run gunicorn as a service
```bash
sudo cp deploy/gunicorn.service /etc/systemd/system/laborhub.service
# Edit User/Group/paths in the unit if needed (Group=apache on RHEL).
sudo systemctl daemon-reload
sudo systemctl enable --now laborhub
sudo systemctl status laborhub
curl -I http://127.0.0.1:8000/            # sanity check
```
Ensure the app user can write to `media/`, and the Apache group can read `staticfiles/`
and `media/`.

## 5. Configure Apache
```bash
sudo cp deploy/apache/laborhub.conf /etc/apache2/sites-available/laborhub.conf
# Edit ServerName, SSL cert paths, and the /var/www/laborhub paths.
sudo a2enmod proxy proxy_http headers ssl
sudo a2ensite laborhub
sudo apachectl configtest && sudo systemctl reload apache2
```
On RHEL, drop the file in `/etc/httpd/conf.d/` instead, ensure the modules load, and
`systemctl reload httpd`.

## 6. Verify
```bash
.venv/bin/python manage.py check --deploy         # expect no ERRORS
```
Then over HTTPS in a browser / with curl:
- [ ] `GET /` returns 200 and the CSS loads from `/static/...`.
- [ ] `/admin/` loads and login (a POST) succeeds — confirms CSRF works across the proxy.
- [ ] Uploading a file (avatar/resume/PDF) saves and serves from `/media/`.
- [ ] `GET /healthz/` returns `200 ok` (readiness probe; `503` means the DB is unreachable).
- [ ] If Sentry is configured, trigger a test error and confirm it appears in the dashboard.
- [ ] Once HTTPS is confirmed, raise `SECURE_HSTS_SECONDS` in `.env`
      (e.g. 3600 → 31536000) and restart the service.

## Updating a deployed site
```bash
cd /var/www/laborhub && git pull
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py compress --force
.venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart laborhub
```

## Fallback: Apache mod_wsgi (no gunicorn service)
If you cannot run a long-lived service, serve the app with **mod_wsgi** instead of
gunicorn: install `mod_wsgi` built against the Media3 Python, and in the `:443` vhost
replace the `ProxyPass` / `ProxyPassReverse` lines with a `WSGIDaemonProcess` +
`WSGIProcessGroup` + `WSGIScriptAlias / /var/www/laborhub/nole/wsgi.py` block. Keep the
`/static/` and `/media/` aliases exactly as they are. Everything else in this runbook is
unchanged (skip step 4).

## Operations & incident response

### Health check
- `GET /healthz/` returns `200 ok` (checks the DB with `SELECT 1`); `503` if the DB is
  unreachable. Unauthenticated and dependency-light.
- Point an uptime monitor (UptimeRobot, Better Stack — free tiers) at
  `https://<host>/healthz/` on a 1–5 min interval, alerting to email/Slack, so you learn
  the site is down before users report it.
- The monitor must use the **hostname**, not the bare IP, or Django rejects it via
  `ALLOWED_HOSTS` (400).

### Error tracking (Sentry)
- Unhandled exceptions are reported to Sentry when `SENTRY_DSN` is set in `.env` (a no-op
  otherwise). The Django integration is enabled automatically by `sentry-sdk`.
- Create a project at sentry.io (or self-host **GlitchTip** — same SDK/DSN), copy the DSN
  into `.env`, set `SENTRY_ENVIRONMENT=production`, and restart the service.
- Optional env: `SENTRY_TRACES_SAMPLE_RATE` (performance tracing, default `0.0`),
  `SENTRY_SEND_PII` (attach user/IP to events, default `0`), `SENTRY_RELEASE` (tag deploys,
  e.g. the git SHA, for regression tracking).
- Configure Sentry alert rules (email/Slack on new or regressed issues).

### Logs
- **App / gunicorn:** logged to stdout → journald. Tail with `journalctl -u laborhub -f`
  (or `-n 200`). Verbosity via `DJANGO_LOGLEVEL` in `.env`.
- **Apache access/error:** in Media3's Apache log directory; Media3 retains HTTP/SSL
  access + error logs for 90 days.
- Under the mod_wsgi fallback (no gunicorn service), app logs go to the Apache error log
  instead of journald.

### Scheduled jobs (cron)
Email digests are sent by a management command. Add to the app user's crontab:
```cron
# Weekly digest — Mondays 07:00
0 7 * * 1  cd /var/www/laborhub && .venv/bin/python manage.py send_digests --frequency weekly
# Monthly digest — 1st of the month 07:00
0 7 1 * *  cd /var/www/laborhub && .venv/bin/python manage.py send_digests --frequency monthly
```
Use `--dry-run` to preview recipients without sending. Requires SMTP configured
(`EMAIL_*` in `.env`); otherwise mail uses the console backend and is not delivered.

### Database backup & restore
Media3 manages the MySQL infrastructure, but **confirm whether application-level backups
are included**; if not, run your own nightly dump:
```cron
# Nightly mysqldump 02:00 (credentials sourced from a root-only env file)
0 2 * * *  mysqldump --single-transaction -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" | gzip > /var/backups/laborhub/db-$(date +\%F).sql.gz
```
Keep dumps **off the VM** (Media3 backup space or S3) and prune old ones. Restore:
```bash
gunzip < db-YYYY-MM-DD.sql.gz | mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME"
```
Also back up uploaded files in `media/` (or use the S3 storage option). **Test a restore
into a scratch database at least once** — an untested backup is not a backup.

### Deploy rollback
```bash
cd /var/www/laborhub
git log --oneline -n 10                 # find the last-good commit/tag
git checkout <good-sha-or-tag>
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py compress --force && .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart laborhub
```
> **Migrations do not auto-reverse on `git checkout`.** If the bad release added a
> migration, reverse it explicitly *before* checking out the old code:
> `manage.py migrate <app> <previous_migration>`. Prefer additive, backwards-compatible
> migrations so a code rollback never requires a schema rollback. Tag releases
> (`git tag -a vX.Y -m ...`) so "last good" is unambiguous.

### Secret rotation
- **`DJANGO_SECRET_KEY`:** generate a new value
  (`python -c "import secrets; print(secrets.token_urlsafe(64))"`), update `.env`, restart.
  This **invalidates all sessions** (everyone is logged out) and outstanding signed tokens
  (e.g. password-reset links), so rotate during low traffic.
- **DB / SMTP / AWS / Sentry credentials:** update in `.env` (keep it `chmod 600`) and
  restart. Never commit secrets — `.env` is git-ignored.

### "Site is down" triage
1. `curl -I https://<host>/healthz/` — `200`? then app + DB are up; suspect Apache/TLS/DNS.
   Non-200 or timeout → continue.
2. `sudo systemctl status laborhub` and `journalctl -u laborhub -n 100` — is gunicorn
   running, or crash-looping?
3. Check **Sentry** for a spike or a new issue with a stack trace.
4. `df -h` (disk full?) and MySQL reachable
   (`mysqladmin -h "$DB_HOST" -u "$DB_USER" -p ping`)?
5. Apache: `sudo apachectl configtest` then reload; check the Apache error log.
6. Was there a recent deploy? **Roll back** (above) to the last-good tag while you
   investigate.
