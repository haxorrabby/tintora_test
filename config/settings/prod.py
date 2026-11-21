"""
Production Settings for Tintora Madrid.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False

# Serve collected static assets when a reverse-proxy static server is not present.
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

# ---------------------------------------------------------------------------
# Secret key: production REQUIRES a real, random SECRET_KEY (>= 50 chars).
# The base.py fallback is a dev-only placeholder and must never be honored
# in production — fail loudly instead of running with a known key.
# ---------------------------------------------------------------------------
if (
    len(SECRET_KEY) < 50
    or SECRET_KEY.startswith("django-insecure-")
    or SECRET_KEY.startswith("unsafe-fallback")
):
    raise ImproperlyConfigured(
        "SECRET_KEY must be provided via the SECRET_KEY environment variable "
        "with a random value of 50+ characters in production."
    )

# Security & SSL
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Email backend (configured for production SMTP / Resend / Sendgrid)
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="smtp.sendgrid.net")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Tintora <hola@tintora.es>")

# Production storage: S3 / MinIO if enabled
if USE_S3:
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="eu-west-3")
    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

# Cache: Redis in production (provisioned in docker-compose.prod.yml)
REDIS_URL = env("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }

# Error tracking: initialised only when a DSN is configured
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.0,
        send_default_pii=False,
    )
