"""Django settings for the wind forecast API.

There is no database: the API reads the Elexon data from JSON files at startup.
"""
import os
from datetime import date, time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Secrets and switches come from environment variables, with safe local defaults.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-not-a-secret")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

# --- 2. What Django loads --------------------------------------------------
# Only what we use: CORS support, the REST toolkit, and our own app.
INSTALLED_APPS = [
    "corsheaders",
    "rest_framework",
    "forecasts"
]

# Code that wraps every request. CORS first, so it can answer browser pre-flight checks.
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "windapp.urls"
WSGI_APPLICATION = "windapp.wsgi.application"

DATABASES = {}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TIME_ZONE = "UTC"
USE_TZ = True

# The React front end runs on another address, so the browser needs permission to call us.
# Safe here because the API is read-only and public.
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_METHODS = ["GET", "OPTIONS"]

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}

# Where the files written by scripts/ingest_elexon.py live.
DATA_DIR = Path(os.environ.get("WIND_DATA_DIR", BASE_DIR / "data"))

DECISION_WINDOW = (date(2026, 1, 1), date(2026, 1, 31))

DEFAULT_CUTOFF = time(9, 0)