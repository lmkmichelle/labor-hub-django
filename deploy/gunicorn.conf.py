"""gunicorn configuration for the Labor Hub app on Media3.

Run via:  gunicorn -c deploy/gunicorn.conf.py nole.wsgi:application
The systemd unit in deploy/gunicorn.service invokes exactly this.
"""

import multiprocessing
import os

# Bind to loopback only; Apache reverse-proxies public traffic to this address.
bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8000")

# Rule of thumb: (2 x CPU cores) + 1. Override with the WEB_CONCURRENCY env var.
workers = int(os.environ.get("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))

# Recycle workers periodically to bound memory growth.
max_requests = 1000
max_requests_jitter = 100

timeout = 60
graceful_timeout = 30
keepalive = 5

# Log to stdout/stderr so journald (systemd) captures everything.
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOGLEVEL", "info")

# Trust X-Forwarded-* only from the local Apache proxy.
forwarded_allow_ips = "127.0.0.1"
