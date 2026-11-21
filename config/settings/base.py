"""
Django Base Settings for Tintora Madrid.
"""

from pathlib import Path

import environ
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, "unsafe-fallback-key-replace-with-env"),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    ADMIN_URL_PATH=(str, "gestion-tintora/"),
    USE_S3=(bool, False),
)

# Read .env file if present
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
ADMIN_URL_PATH = env("ADMIN_URL_PATH")
USE_S3 = env.bool("USE_S3", default=False)

# Application definition
INSTALLED_APPS = [
    # Unfold Admin Theme (must precede django.contrib.admin)
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sitemaps",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third Party
    "axes",
    "rest_framework",
    # Local Domain Apps
    "apps.core",
    "apps.dashboard.apps.DashboardConfig",
    "apps.accounts",
    "apps.catalog",
    "apps.quotes",
    "apps.cart",
    "apps.orders",
    "apps.payments",
    "apps.blog",
    "apps.latin_products",
]

AUTH_USER_MODEL = "accounts.CustomUser"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "apps.accounts.backends.EmailOrUsernameModelBackend",
    "django.contrib.auth.backends.ModelBackend",
]
LOGIN_URL = "customer:login"
LOGIN_REDIRECT_URL = "customer:dashboard"
LOGOUT_REDIRECT_URL = "core:home"
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"]
ADMIN_ALLOWED_IPS = env.list("ADMIN_ALLOWED_IPS", default=[])
ADMIN_SESSION_IDLE_TIMEOUT = env.int("ADMIN_SESSION_IDLE_TIMEOUT", default=30 * 60)
# Enforce TOTP two-factor authentication for staff/admin access. Secure by
# default; local development overrides this to False (see dev.py) and any
# environment can toggle it explicitly with the ADMIN_2FA_REQUIRED env var.
ADMIN_2FA_REQUIRED = env.bool("ADMIN_2FA_REQUIRED", default=True)
TOTP_ENCRYPTION_KEY = env("TOTP_ENCRYPTION_KEY", default=SECRET_KEY)
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True

CSP_DEFAULT_SRC = ["'self'"]
CSP_SCRIPT_SRC = ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https://unpkg.com"]
CSP_STYLE_SRC = ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"]
CSP_FONT_SRC = ["'self'", "data:", "https://fonts.gstatic.com"]
CSP_IMG_SRC = ["'self'", "data:", "blob:", "https:"]
CSP_CONNECT_SRC = ["'self'"]
CSP_FRAME_ANCESTORS = ["'none'"]
CSP_OBJECT_SRC = ["'none'"]
CSP_BASE_URI = ["'self'"]
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https://unpkg.com"],
        "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
        "font-src": ["'self'", "data:", "https://fonts.gstatic.com"],
        "img-src": ["'self'", "data:", "blob:", "https:"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
    }
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",  # i18n support (/es/, /en/)
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",
    "csp.middleware.CSPMiddleware",
    "apps.dashboard.middleware.AuditActorMiddleware",
    "apps.dashboard.middleware.AdminSecurityMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                # Custom Tintora Context Processors
                "apps.core.context_processors.tintora_globals",
                "apps.core.context_processors.seo_globals",
                "apps.cart.context_processors.cart_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database configuration
DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization & Localization (Spain / EU)
LANGUAGE_CODE = "es"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ("es", _("Español")),
    ("en", _("English")),
]

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Cache — local memory by default; production overrides with Redis (see prod.py)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "tintora-cache",
    }
}

# Logging — console everywhere; production adds request/error detail via root logger
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": env("APP_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery & Redis Settings
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Payment Gateways
# Stripe is disabled for now — enable later with PAYMENTS_STRIPE_ENABLED=True + keys
PAYMENTS_STRIPE_ENABLED = env.bool("PAYMENTS_STRIPE_ENABLED", default=False)
# Accept both env var names so either .env convention works.
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="") or env("STRIPE_PUBLIC_KEY", default="")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")

# Redsys / Bizum (leave empty → simulation mode in development)
REDSYS_MERCHANT_CODE = env("REDSYS_MERCHANT_CODE", default="")
REDSYS_SECRET_KEY = env("REDSYS_SECRET_KEY", default="")
REDSYS_TERMINAL = env("REDSYS_TERMINAL", default="001")
REDSYS_URL = env(
    "REDSYS_URL",
    default="https://sis-t.redsys.es:25443/sis/realizarPago",
)

# Bank transfer details shown to customers
TINTORA_BANK_IBAN = env("TINTORA_BANK_IBAN", default="ES76 0049 1500 0512 3456 7890")
TINTORA_BANK_BIC = env("TINTORA_BANK_BIC", default="BSCHESMMXXX")

# Email (override in prod.py for SMTP)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Tintora <hola@tintora.es>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Spanish VAT / Tax & Company Information
TINTORA_IVA_PERCENTAGE = 21
TINTORA_COMPANY = {
    "NAME": env("COMPANY_NAME", default="Tintora Impresión y Soluciones Creativas S.L."),
    "NIF_CIF": env("COMPANY_NIF_CIF", default="B-88776655"),
    "ADDRESS": env(
        "COMPANY_ADDRESS",
        default="C. Núñez de Balboa, 30, Loc 1, 28902 Getafe, Madrid, Spain",
    ),
    "PHONE": env("COMPANY_PHONE", default="+34 631 51 76 44"),
    "WHATSAPP": env("COMPANY_WHATSAPP", default="+34 631 51 76 44"),
    "EMAIL": env("COMPANY_EMAIL", default="hola@tintora.es"),
    "OPENING_HOURS": "Lunes a Viernes: 09:30 - 19:30 | Sábados: 10:00 - 14:00",
    "LOCATION_CITY": "Getafe",
    "COUNTRY": "España",
}

# Unfold Admin Theme Styling Configuration
UNFOLD = {
    "SITE_TITLE": "Tintora Madrid — Panel de Control",
    "SITE_HEADER": "Tintora",
    "SITE_SUBHEADER": "Estudio de Impresión & Soluciones Creativas",
    "SITE_SYMBOL": "print",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SHOW_LANGUAGES": True,
    "COLORS": {
        "primary": {
            "50": "254 242 242",
            "100": "254 226 226",
            "200": "254 202 202",
            "300": "252 165 165",
            "400": "248 113 113",
            "500": "232 57 43",  # Tintora Vermilion
            "600": "220 38 38",
            "700": "185 28 28",
            "800": "153 27 27",
            "900": "127 29 29",
            "950": "69 10 10",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": _("Catálogo & Producción"),
                "separator": True,
                "items": [
                    {
                        "title": _("Productos"),
                        "icon": "inventory_2",
                        "link": lambda request: reverse_lazy("admin:catalog_product_changelist"),
                    },
                    {
                        "title": _("Categorías"),
                        "icon": "category",
                        "link": lambda request: reverse_lazy("admin:catalog_category_changelist"),
                    },
                    {
                        "title": _("Opciones de Configuración"),
                        "icon": "tune",
                        "link": lambda request: reverse_lazy("admin:catalog_productoptiongroup_changelist"),
                    },
                ],
            },
            {
                "title": _("Desarrollo Web & Leads"),
                "separator": True,
                "items": [
                    {
                        "title": _("Solicitudes de Presupuesto"),
                        "icon": "assignment",
                        "link": lambda request: reverse_lazy("admin:quotes_quoterequest_changelist"),
                    },
                    {
                        "title": _("Paquetes de Servicios Web"),
                        "icon": "devices",
                        "link": lambda request: reverse_lazy("admin:quotes_webpackage_changelist"),
                    },
                    {
                        "title": _("Portfolio de Desarrollo Web"),
                        "icon": "web",
                        "link": lambda request: reverse_lazy("admin:quotes_webportfolioproject_changelist"),
                    },
                    {
                        "title": _("Registro de Auditoría"),
                        "icon": "manage_search",
                        "link": lambda request: reverse_lazy("admin:dashboard_auditevent_changelist"),
                    },
                ],
            },
            {
                "title": _("Clientes & Permisos"),
                "separator": True,
                "items": [
                    {
                        "title": _("Clientes y Usuarios"),
                        "icon": "people",
                        "link": lambda request: reverse_lazy("admin:accounts_customuser_changelist"),
                    },
                    {
                        "title": _("Grupos de Rol"),
                        "icon": "admin_panel_settings",
                        "link": lambda request: reverse_lazy("admin:auth_group_changelist"),
                    },
                ],
            },
        ],
    },
}
