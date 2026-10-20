from datetime import timedelta
from pathlib import Path
import sys
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
import environ


BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    SECURE_SSL_REDIRECT=(bool, False),
    SESSION_COOKIE_SECURE=(bool, False),
    CSRF_COOKIE_SECURE=(bool, False),
    SECURE_HSTS_SECONDS=(int, 0),
)
env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="").strip()
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY is required in the environment.")

DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1"] if DEBUG else [],
)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

if not DEBUG:
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "ALLOWED_HOSTS must explicitly list production hosts when DEBUG=False."
        )
    if not CSRF_TRUSTED_ORIGINS or any(
        urlsplit(origin).scheme != "https" or not urlsplit(origin).netloc
        for origin in CSRF_TRUSTED_ORIGINS
    ):
        raise ImproperlyConfigured(
            "CSRF_TRUSTED_ORIGINS must explicitly list HTTPS origins when DEBUG=False."
        )

INSTALLED_APPS = [
    "core.admin_config.ProjectVybeAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "cloudinary",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "axes",
    "solo",
    "core",
    "legal",
    "catalog",
    "blog",
    "courses",
    "leads",
    "orders",
    "pages",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "core.middleware.MaintenanceModeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Must be last: turns a locked-out login into a 429 response.
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"

# Friendly page when a form is sent with an expired or missing CSRF token.
CSRF_FAILURE_VIEW = "core.views.csrf_failure"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.public_site_config",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

def _database_configuration():
    database_url = env("DATABASE_URL", default="").strip()

    if not database_url:
        if DEBUG:
            return env.db_url(
                "DATABASE_URL",
                default=f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}",
            )
        raise ImproperlyConfigured(
            "DATABASE_URL is required when DEBUG=False; production cannot use SQLite."
        )

    parsed_database_url = urlsplit(database_url)
    if not DEBUG and (
        parsed_database_url.scheme.lower() not in {"postgres", "postgresql"}
        or not parsed_database_url.netloc
        or not parsed_database_url.path.strip("/")
    ):
        raise ImproperlyConfigured(
            "DATABASE_URL must be a valid PostgreSQL URL when DEBUG=False."
        )

    try:
        database = env.db_url("DATABASE_URL")
    except Exception:
        raise ImproperlyConfigured(
            "DATABASE_URL must be a valid database URL when DEBUG=False."
        ) from None

    if not DEBUG and database.get("ENGINE") == "django.db.backends.sqlite3":
        raise ImproperlyConfigured(
            "DATABASE_URL must point to PostgreSQL when DEBUG=False."
        )

    return database


DATABASES = {"default": _database_configuration()}
# Reuse connections between requests (Neon adds TLS handshake latency) and
# reopen any connection Neon dropped while the compute was suspended.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# How long the navigation categories stay cached (0 disables; tests use 0).
NAVIGATION_CATEGORIES_CACHE_SECONDS = env.int(
    "NAVIGATION_CATEGORIES_CACHE_SECONDS",
    default=0 if "test" in sys.argv else 300,
)

# Cloudflare Turnstile (bot check on public forms). Both unset = disabled.
TURNSTILE_SITE_KEY = env("TURNSTILE_SITE_KEY", default="").strip()
TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY", default="").strip()

# FAQs are cached for five minutes (0 under test) and cleared whenever one is saved.
FAQ_CACHE_SECONDS = env.int("FAQ_CACHE_SECONDS", default=0 if "test" in sys.argv else 300)

# Razorpay (online payments). Env vars only; never put these in Admin or the repo.
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default="").strip()
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default="").strip()
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET", default="").strip()
# Only change this to point at a local fake gateway while developing.
RAZORPAY_API_BASE = env("RAZORPAY_API_BASE", default="https://api.razorpay.com/v1").strip().rstrip("/")

# Site Settings are cached for a minute (production only) so Admin edits show up
# quickly in every worker without a database read on each request.
SOLO_CACHE = None if "test" in sys.argv else "default"
SOLO_CACHE_TIMEOUT = 60

# Footer legal links are cached and cleared whenever a legal page changes (0 under test).
LEGAL_FOOTER_CACHE_SECONDS = env.int(
    "LEGAL_FOOTER_CACHE_SECONDS",
    default=0 if "test" in sys.argv else 300,
)

# Per-process cache: enough for rate limits and the navigation categories.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "projectvybe",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    # Axes first so it can refuse logins from locked-out IPs.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Admin login protection: 5 failures from one IP lock that IP out for an hour.
# Locking by IP (not username) stops an attacker locking the real admin out.
AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = timedelta(hours=1)
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
AXES_RESET_ON_SUCCESS = True
# Behind Render's proxy REMOTE_ADDR is the proxy, so reuse our trusted-proxy logic.
AXES_CLIENT_IP_CALLABLE = "core.ratelimit.client_ip"

OTP_TOTP_ISSUER = "ProjectVybe"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG or "test" in sys.argv
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SITE_URL = env("SITE_URL", default="http://localhost:8000").strip().rstrip("/")
if not DEBUG:
    site_url = urlsplit(SITE_URL)
    if site_url.scheme != "https" or not site_url.netloc:
        raise ImproperlyConfigured(
            "SITE_URL must be an HTTPS public origin when DEBUG=False."
        )
SITE_NAME = env("SITE_NAME", default="ProjectVybe")
SITE_DESCRIPTION = env(
    "SITE_DESCRIPTION",
    default="ProjectVybe helps people build, learn, and grow through thoughtful technology projects and services.",
)
WHATSAPP_NUMBER = env("WHATSAPP_NUMBER", default="")
PUBLIC_CONTACT_EMAIL = env("PUBLIC_CONTACT_EMAIL", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=PUBLIC_CONTACT_EMAIL)
# Sender for payment, receipt and delivery emails. Falls back to the enquiries sender.
ORDERS_FROM_EMAIL = env("ORDERS_FROM_EMAIL", default=DEFAULT_FROM_EMAIL)
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default=(
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
# Send enquiry emails from a background thread so visitors never wait on SMTP.
ENQUIRY_EMAIL_ASYNC = env.bool(
    "ENQUIRY_EMAIL_ASYNC", default=not DEBUG and "test" not in sys.argv
)
ENQUIRY_RATE_LIMIT = env.int("ENQUIRY_RATE_LIMIT", default=5)
ENQUIRY_RATE_WINDOW = env.int("ENQUIRY_RATE_WINDOW", default=600)
SEARCH_RATE_LIMIT = env.int("SEARCH_RATE_LIMIT", default=60)
# Admin lives at a configurable path (set ADMIN_URL on Render to something private).
ADMIN_URL = env("ADMIN_URL", default="admin/").strip().strip("/") or "admin"
ADMIN_URL += "/"
# Number of trusted reverse proxies (Render = 1) when reading the client IP.
TRUSTED_PROXY_COUNT = env.int("TRUSTED_PROXY_COUNT", default=0 if DEBUG else 1)
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=60 * 60 * 8)
CLOUDINARY_URL = env("CLOUDINARY_URL", default="")
CLOUDINARY = {
    "secure": True,
}

SECURE_PROXY_SSL_HEADER = None if DEBUG else ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT", default=not DEBUG)
SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE", default=not DEBUG)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS", default=31536000 if not DEBUG else 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)
SECURE_HSTS_PRELOAD = env("SECURE_HSTS_PRELOAD", default=False)

if not DEBUG and (not SECURE_SSL_REDIRECT or not SESSION_COOKIE_SECURE or not CSRF_COOKIE_SECURE):
    raise ImproperlyConfigured(
        "HTTPS redirect and secure cookies must be enabled when DEBUG=False."
    )

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
