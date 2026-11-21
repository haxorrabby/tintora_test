from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel
from apps.orders.models import Order


class Payment(TimeStampedModel):
    class Gateway(models.TextChoices):
        STRIPE = "stripe", _("Stripe (Tarjeta de Crédito / Débito)")
        BIZUM = "bizum", _("Bizum")
        REDSYS = "redsys", _("Redsys (TPV Virtual)")
        TRANSFER = "transfer", _("Transferencia Bancaria")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pendiente de pago")
        COMPLETED = "completed", _("Completado")
        FAILED = "failed", _("Fallido")
        REFUNDED = "refunded", _("Reembolsado")

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name=_("Pedido"),
    )
    gateway = models.CharField(
        _("Pasarela de pago"),
        max_length=20,
        choices=Gateway.choices,
        default=Gateway.STRIPE,
    )
    transaction_id = models.CharField(
        _("Identificador de transacción / Pago"),
        max_length=150,
        blank=True,
        db_index=True,
    )
    amount = models.DecimalField(
        _("Importe cobrado (€)"),
        max_digits=10,
        decimal_places=2,
    )
    currency = models.CharField(
        _("Moneda"),
        max_length=3,
        default="EUR",
    )
    status = models.CharField(
        _("Estado de la transacción"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    raw_response = models.JSONField(
        _("Respuesta de la pasarela"),
        default=dict,
        blank=True,
    )
    error_message = models.TextField(_("Mensaje de error"), blank=True)

    class Meta:
        verbose_name = _("Transacción de pago")
        verbose_name_plural = _("Transacciones de pago")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.get_gateway_display()}] {self.order.order_number} · {self.amount}€ ({self.get_status_display()})"
