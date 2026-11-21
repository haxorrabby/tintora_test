"""
Development Settings for Tintora Madrid.
"""

from .base import *

DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = ["*"]

# Console email backend for quick inspection in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Two-factor auth is optional in local development so staff can browse the
# admin without provisioning an authenticator app. Production keeps the secure
# default (True) from base.py. Set ADMIN_2FA_REQUIRED=True to test the flow.
ADMIN_2FA_REQUIRED = env.bool("ADMIN_2FA_REQUIRED", default=False)

# Static files handling in development
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Run Celery tasks inline (no broker/worker needed). Order confirmation and
# quote emails execute synchronously, so checkout and tests never block on a
# dead Redis connection. Production keeps the real broker (see prod.py).
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Session cookie configurations for development
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
