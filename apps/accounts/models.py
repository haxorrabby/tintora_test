from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class CustomUser(AbstractUser):
    class CustomerType(models.TextChoices):
        INDIVIDUAL = "individual", _("Particular")
        BUSINESS = "business", _("Empresa / Autónomo")

    email = models.EmailField(_("Correo electrónico"), unique=True)
    customer_type = models.CharField(
        _("Tipo de cliente"),
        max_length=20,
        choices=CustomerType.choices,
        default=CustomerType.INDIVIDUAL,
    )
    company_name = models.CharField(_("Razón Social / Empresa"), max_length=255, blank=True)
    nif_cif = models.CharField(
        _("NIF / CIF / NIE"),
        max_length=30,
        blank=True,
        help_text=_("Obligatorio para la emisión de facturas oficiales en España"),
    )
    phone = models.CharField(_("Teléfono de contacto"), max_length=30, blank=True)

    # Primary billing/shipping address
    address = models.CharField(_("Dirección"), max_length=255, blank=True)
    postal_code = models.CharField(_("Código Postal"), max_length=10, blank=True)
    city = models.CharField(_("Ciudad"), max_length=100, default="Madrid")
    province = models.CharField(_("Provincia"), max_length=100, default="Madrid")
    country = models.CharField(_("País"), max_length=100, default="España")

    # Security & Preferences
    is_verified = models.BooleanField(_("Email verificado"), default=False)
    newsletter_subscribed = models.BooleanField(_("Suscrito a la Gaceta Tintora"), default=False)
    totp_secret = models.CharField(_("Secreto TOTP del personal"), max_length=255, blank=True, editable=False)
    totp_enabled = models.BooleanField(_("Verificación en dos pasos activa"), default=False)
    created_at = models.DateTimeField(_("Fecha de registro"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Última actualización"), auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = _("Usuario")
        verbose_name_plural = _("Usuarios & Clientes")
        ordering = ["-created_at"]

    def __str__(self):
        if self.customer_type == self.CustomerType.BUSINESS and self.company_name:
            return f"{self.company_name} ({self.email})"
        full_name = self.get_full_name()
        return f"{full_name} ({self.email})" if full_name else self.email


class SavedAddress(TimeStampedModel):
    """Customer saved addresses for quick checkout"""
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="saved_addresses",
        verbose_name=_("Cliente"),
    )
    label = models.CharField(_("Etiqueta"), max_length=50, help_text=_("Ej: Oficina, Casa, Almacén"))
    address_line1 = models.CharField(_("Dirección línea 1"), max_length=255)
    address_line2 = models.CharField(_("Dirección línea 2"), max_length=255, blank=True)
    postal_code = models.CharField(_("Código Postal"), max_length=10)
    city = models.CharField(_("Ciudad"), max_length=100)
    province = models.CharField(_("Provincia"), max_length=100)
    country = models.CharField(_("País"), max_length=100, default="España")
    is_default = models.BooleanField(_("Dirección por defecto"), default=False)

    class Meta:
        verbose_name = _("Dirección guardada")
        verbose_name_plural = _("Direcciones guardadas")
        ordering = ["-is_default", "label"]

    def __str__(self):
        return f"{self.label} - {self.city}"


class Wishlist(TimeStampedModel):
    """Customer wishlist for products"""
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
        verbose_name=_("Cliente"),
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="wishlist_entries",
        verbose_name=_("Producto"),
    )
    notes = models.TextField(_("Notas"), blank=True, help_text=_("Notas personales sobre este producto"))

    class Meta:
        verbose_name = _("Deseo")
        verbose_name_plural = _("Lista de deseos")
        ordering = ["-created_at"]
        unique_together = ["user", "product"]

    def __str__(self):
        return f"{self.user.email} - {self.product.name}"
