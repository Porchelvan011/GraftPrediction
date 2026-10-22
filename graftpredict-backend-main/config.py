import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

DEBUG = str(os.environ.get("DEBUG", "0")).lower() in ("1", "true", "yes")
SECRET_KEY = os.environ.get("SECRET_KEY") if not DEBUG else os.environ.get("SECRET_KEY") or "graftpredict-dev-secret-2026"
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "graftpredict")
DB_POOL_NAME = os.environ.get("DB_POOL_NAME", "graftpredict_pool")
DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", 5))

MAIL_SERVER = os.environ.get("MAIL_SERVER")
MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
MAIL_USE_TLS = str(os.environ.get("MAIL_USE_TLS", "true")).lower() in ("1","true","yes")
MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER") or MAIL_USERNAME

CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",") if o.strip()]

DEBUG_SHOW_OTP = str(os.environ.get("DEBUG_SHOW_OTP", "0")).lower() in ("1", "true", "yes")

USE_S3 = str(os.environ.get("USE_S3", "0")).lower() in ("1","true","yes")
S3_BUCKET = os.environ.get("S3_BUCKET")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
S3_REGION = os.environ.get("S3_REGION")

MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))

GUNICORN_WORKERS = int(os.environ.get("GUNICORN_WORKERS", 2))

BROKER_URL = os.environ.get("BROKER_URL")

# Basic validation
if not DEBUG and not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is required in production")

if not DEBUG and not GOOGLE_CLIENT_ID:
    raise RuntimeError("GOOGLE_CLIENT_ID is required in production")
