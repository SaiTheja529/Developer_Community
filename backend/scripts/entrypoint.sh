#!/bin/sh
# Container entrypoint: apply migrations under an advisory lock, then start gunicorn.
set -e
flask --app wsgi db-upgrade-locked
exec gunicorn -c gunicorn.conf.py wsgi:app
