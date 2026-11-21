from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LatinProductsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.latin_products"
    verbose_name = _("Productos Latinos")
