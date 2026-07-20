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
