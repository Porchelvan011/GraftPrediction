"""WSGI entrypoint for production servers (gunicorn, uWSGI, etc.)

Example gunicorn invocation (from project root):
    gunicorn -w 4 -b 0.0.0.0:5000 Backend.wsgi:app
"""

from complete_backend import app  # noqa: F401


# `app` is imported by WSGI servers; do not start a dev server here.
