"""Gunicorn settings. gthread workers are required for SSE streaming (spec §2, §16.2)."""

import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8080")
worker_class = "gthread"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "16"))
timeout = 120
graceful_timeout = 30
keepalive = 5
accesslog = None  # the app writes its own JSON access log
