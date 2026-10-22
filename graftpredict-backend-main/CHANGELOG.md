# Changelog

## Unreleased
- Centralized configuration in `config.py`.
- Added DB connection pool in `db.py` and pooled compat connector.
- Centralized JWT decoding and `require_auth` decorator in `auth.py`.
- OTP sending made asynchronous via `email_worker.py` (thread fallback).
- PDFs persisted to filesystem via `storage.py`; migration script added.
- Added health endpoints `/healthz` and `/readyz`.
- Added rate limiting for auth and OTP endpoints.
- Added Dockerfile, systemd and Nginx examples, and CI workflow.
- Security hardening: secrets only from env, debug-only fallbacks, CORS restriction.
