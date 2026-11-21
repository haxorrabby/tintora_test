import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.catalog.models import Product
from apps.core.models import TimeStampedModel


class Order(TimeStampedModel):
    class CustomerType(models.TextChoices):
        INDIVIDUAL = "individual", _("Particular / Autónomo")
        BUSINESS = "business", _("Empresa / Sociedad (CIF)")

    class Status(models.TextChoices):
        RECIBIDO = "recibido", _("Recibido")
        REVISION_ARTE = "revision_arte", _("Revisión de arte (Fogra39)")
        PRUEBA_ENVIADA = "prueba_enviada", _("Prueba enviada")
        EN_PRODUCCION = "en_produccion", _("En producción")
        ENVIADO = "enviado", _("Enviado")
        ENTREGADO = "entregado", _("Entregado")
        CANCELADO = "cancelado", _("Cancelado")

    class PaymentMethod(models.TextChoices):
        STRIPE = "stripe", _("Tarjeta Bancaria (Stripe)")
        BIZUM = "bizum", _("Bizum")
        REDSYS = "redsys", _("Redsys (TPV Virtual)")
        TRANSFER = "transfer", _("Transferencia Bancaria")

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", _("Pendiente de pago")
        PAID = "paid", _("Pagado")
        FAILED = "failed", _("Fallido")
        REFUNDED = "refunded", _("Reembolsado")

    order_number = models.CharField(
        _("Número de pedido"),
        max_length=40,
        unique=True,
        db_index=True,
    )
    access_token = models.UUIDField(
        _("Token de acceso"),
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        help_text=_("Permite consultar confirmación y factura sin iniciar sesión"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name=_("Usuario"),
    )

    # Customer Fiscal Details (Spanish legal requirement)
    customer_type = models.CharField(
        _("Tipo de cliente"),
        max_length=20,
        choices=CustomerType.choices,
        default=CustomerType.INDIVIDUAL,
    )
    email = models.EmailField(_("Correo electrónico"))
    first_name = models.CharField(_("Nombre"), max_length=100)
    last_name = models.CharField(_("Apellidos"), max_length=100)
    phone = models.CharField(_("Teléfono de contacto"), max_length=30)
    company_name = models.CharField(_("Razón Social"), max_length=150, blank=True)
    nif_cif = models.CharField(
        _("NIF / CIF / NIE"),
        max_length=20,
        help_text=_("Requerido para la emisión de factura española conforme a normativa tributaria"),
    )

    # Delivery & Shipping Information
    shipping_address_line1 = models.CharField(_("Dirección de envío"), max_length=200)
    shipping_address_line2 = models.CharField(_("Piso, puerta, escalera (opcional)"), max_length=100, blank=True)
    shipping_postal_code = models.CharField(_("Código Postal"), max_length=10)
    shipping_city = models.CharField(_("Ciudad / Localidad"), max_length=100)
    shipping_province = models.CharField(_("Provincia"), max_length=100, default="Madrid")
    shipping_country = models.CharField(_("País"), max_length=100, default="España")

    shipping_method_name = models.CharField(_("Servicio de transporte"), max_length=150)
    courier = models.CharField(_("Transportista"), max_length=50, default="SEUR")
    tracking_number = models.CharField(_("Número de seguimiento"), max_length=100, blank=True)
    tracking_url = models.URLField(_("Enlace de tracking"), blank=True)

    # Status Workflow
    status = models.CharField(
        _("Estado del pedido"),
        max_length=25,
        choices=Status.choices,
        default=Status.RECIBIDO,
    )
    payment_method = models.CharField(
        _("Método de pago"),
        max_length=25,
        choices=PaymentMethod.choices,
        default=PaymentMethod.TRANSFER,
    )
    payment_status = models.CharField(
        _("Estado del pago"),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    # Amounts & Fiscal Breakdown (Spain IVA 21%)
    subtotal = models.DecimalField(_("Subtotal (€)"), max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(_("Descuento (€)"), max_digits=10, decimal_places=2, default=Decimal("0.00"))
    coupon_code = models.CharField(_("Cupón canjeado"), max_length=40, blank=True)
    shipping_cost = models.DecimalField(_("Portes de envío (€)"), max_digits=8, decimal_places=2, default=Decimal("0.00"))

    taxable_base = models.DecimalField(_("Base Imponible (€)"), max_digits=10, decimal_places=2)
    iva_percentage = models.DecimalField(_("IVA (%)"), max_digits=4, decimal_places=1, default=Decimal("21.0"))
    iva_amount = models.DecimalField(_("Cuota IVA (€)"), max_digits=10, decimal_places=2)
    total = models.DecimalField(_("Total a pagar (€)"), max_digits=10, decimal_places=2)

    customer_notes = models.TextField(_("Instrucciones de entrega / notas del cliente"), blank=True)
    internal_notes = models.TextField(_("Notas internas de taller"), blank=True)
    confirmation_email_sent = models.BooleanField(
        _("Email de confirmación enviado"),
        default=False,
    )

    class Meta:
        verbose_name = _("Pedido")
        verbose_name_plural = _("Pedidos")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.order_number} · {self.full_name} ({self.total}€)"

    @property
    def full_name(self) -> str:
        if self.customer_type == self.CustomerType.BUSINESS and self.company_name:
            return f"{self.company_name} ({self.first_name} {self.last_name})"
        return f"{self.first_name} {self.last_name}"

    @property
    def is_paid(self) -> bool:
        return self.payment_status == self.PaymentStatus.PAID

    def generate_order_number(self) -> str:
        """Delegates to race-safe allocator in services (kept for admin/scripts)."""
        from apps.orders.services import allocate_order_number

        return allocate_order_number()


class OrderItem(TimeStampedModel):
    class ArtworkStatus(models.TextChoices):
        DESIGN_LATER = "design_later", _("Diseñar más tarde")
        UPLOADED = "uploaded", _("Arte subido")
        APPROVED = "approved", _("Aprobado")
        REJECTED = "rejected", _("Rechazado")
        NEEDS_REVISION = "needs_revision", _("Necesita revisión")

    class ProofStatus(models.TextChoices):
        NOT_REQUESTED = "not_requested", _("No solicitada")
        PENDING = "pending", _("Pendiente")
        SENT = "sent", _("Enviada")
        APPROVED = "approved", _("Aprobada")
        REJECTED = "rejected", _("Rechazada")

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Pedido"),
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_items",
        verbose_name=_("Producto"),
    )
    product_name = models.CharField(_("Nombre del producto"), max_length=255)
    product_sku = models.CharField(_("SKU"), max_length=50)
    variant_label = models.CharField(_("Tamaño / variante"), max_length=80, blank=True)
    quantity = models.PositiveIntegerField(_("Cantidad"), default=1)
    unit_price = models.DecimalField(_("Precio unitario"), max_digits=10, decimal_places=2)

    # Configuration snapshot
    configuration = models.JSONField(_("Configuración"), default=dict, blank=True)

    # Artwork & Proof
    artwork_status = models.CharField(
        _("Estado del arte"),
        max_length=20,
        choices=ArtworkStatus.choices,
        default=ArtworkStatus.DESIGN_LATER,
    )
    artwork_file = models.FileField(_("Archivo de arte"), upload_to="artwork/%Y/%m/", blank=True, null=True)
    request_proof = models.BooleanField(_("Solicitar prueba física"), default=False)
    proof_status = models.CharField(
        _("Estado de la prueba"),
        max_length=20,
        choices=ProofStatus.choices,
        default=ProofStatus.NOT_REQUESTED,
    )
    proof_feedback = models.TextField(_("Cambios solicitados por el cliente"), blank=True)
    proof_image = models.ImageField(_("Imagen de la prueba"), upload_to="proofs/%Y/%m/", blank=True)
    proof_sent_at = models.DateTimeField(_("Fecha de envío de prueba"), null=True, blank=True)

    line_total = models.DecimalField(_("Total línea"), max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = _("Ítem de pedido")
        verbose_name_plural = _("Ítems de pedido")
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity}× {self.product_name} ({self.line_total}€)"


class Invoice(TimeStampedModel):
    """
    Official Spanish Invoice (Factura Ordinaria) complying with RD 1619/2012.
    Sequential numbering, issuer and customer fiscal data, tax breakdown.
    """
    invoice_number = models.CharField(
        _("Número de factura"),
        max_length=40,
        unique=True,
        db_index=True,
    )
    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name="invoice",
        verbose_name=_("Pedido asociado"),
    )
    issue_date = models.DateField(_("Fecha de emisión"), default=timezone.now)
    pdf_file = models.FileField(
        _("Documento PDF oficial"),
        upload_to="invoices/%Y/%m/",
        blank=True,
        null=True,
    )

    # Fiscal Snapshots
    company_data = models.JSONField(_("Datos fiscales del emisor"), default=dict)
    customer_data = models.JSONField(_("Datos fiscales del receptor"), default=dict)

    taxable_base = models.DecimalField(_("Base Imponible (€)"), max_digits=10, decimal_places=2)
    iva_percentage = models.DecimalField(_("Tipo IVA (%)"), max_digits=4, decimal_places=1, default=Decimal("21.0"))
    iva_amount = models.DecimalField(_("Cuota IVA (€)"), max_digits=10, decimal_places=2)
    total = models.DecimalField(_("Total Factura (€)"), max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(_("Cobrada"), default=False)

    class Meta:
        verbose_name = _("Factura oficial")
        verbose_name_plural = _("Facturas oficiales")
        ordering = ["-issue_date", "-id"]

    def __str__(self) -> str:
        return f"{self.invoice_number} · {self.order.full_name} ({self.total}€)"

    @classmethod
    def generate_next_number(cls) -> str:
        """Delegates to race-safe allocator in services."""
        from apps.orders.services import allocate_invoice_number

        return allocate_invoice_number()
