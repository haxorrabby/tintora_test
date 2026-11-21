from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.catalog.models import Product, ProductOptionValue
from apps.core.models import TimeStampedModel


class ShippingZone(TimeStampedModel):
    class ZoneCode(models.TextChoices):
        MADRID_LOCAL = "madrid_local", _("Madrid Local (Capital & M-30/M-40)")
        PENINSULA = "peninsula", _("España Peninsular")
        BALEARES_CANARIAS = "islas", _("Baleares, Canarias, Ceuta y Melilla")
        UE = "ue", _("Unión Europea")

    code = models.CharField(
        _("Código de zona"),
        max_length=30,
        choices=ZoneCode.choices,
        unique=True,
    )
    name = models.CharField(_("Nombre de la zona"), max_length=120)
    description = models.CharField(_("Cobertura geográfica"), max_length=255, blank=True)
    is_active = models.BooleanField(_("Activa"), default=True)
    order = models.PositiveIntegerField(_("Orden"), default=0)

    class Meta:
        verbose_name = _("Zona de envío")
        verbose_name_plural = _("Zonas de envío")
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_code_display()})"


class ShippingMethod(TimeStampedModel):
    class Courier(models.TextChoices):
        CORREOS = "correos", _("Correos Express")
        SEUR = "seur", _("SEUR")
        MRW = "mrw", _("MRW")
        GLS = "gls", _("GLS")
        PICKUP = "pickup", _("Recogida local en Taller (Getafe)")

    zone = models.ForeignKey(
        ShippingZone,
        on_delete=models.CASCADE,
        related_name="methods",
        verbose_name=_("Zona de envío"),
    )
    courier = models.CharField(
        _("Transportista / Courier"),
        max_length=20,
        choices=Courier.choices,
        default=Courier.SEUR,
    )
    name = models.CharField(_("Nombre del servicio"), max_length=120)
    base_rate = models.DecimalField(
        _("Tarifa base (€ IVA incl.)"),
        max_digits=8,
        decimal_places=2,
        default=Decimal("4.95"),
    )
    per_kg_rate = models.DecimalField(
        _("Suplemento por kg adicional (€)"),
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.50"),
    )
    free_threshold = models.DecimalField(
        _("Envío gratuito a partir de (€)"),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Dejar vacío si no aplica envío gratuito para este servicio"),
    )
    estimated_days = models.CharField(
        _("Plazo de tránsito estimado"),
        max_length=60,
        default="24/48h",
    )
    is_active = models.BooleanField(_("Activo"), default=True)
    order = models.PositiveIntegerField(_("Orden"), default=0)

    class Meta:
        verbose_name = _("Método de envío")
        verbose_name_plural = _("Métodos de envío")
        ordering = ["zone", "order", "base_rate"]

    def __str__(self) -> str:
        return f"[{self.zone.name}] {self.name} — {self.base_rate}€"

    def calculate_cost(self, subtotal: Decimal, weight_grams: int = 0) -> Decimal:
        """Calculate shipping cost in EUR with 21% IVA included."""
        if self.courier == self.Courier.PICKUP:
            return Decimal("0.00")
        if self.free_threshold and subtotal >= self.free_threshold:
            return Decimal("0.00")
        extra_kg = max(0, (weight_grams - 1000) // 1000) if weight_grams > 1000 else 0
        extra_charge = Decimal(extra_kg) * self.per_kg_rate
        return (self.base_rate + extra_charge).quantize(Decimal("0.01"))


class Coupon(TimeStampedModel):
    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", _("Porcentaje (%)")
        FIXED = "fixed", _("Importe fijo (€)")

    code = models.CharField(_("Código del cupón"), max_length=40, unique=True)
    discount_type = models.CharField(
        _("Tipo de descuento"),
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE,
    )
    discount_value = models.DecimalField(
        _("Valor del descuento"),
        max_digits=8,
        decimal_places=2,
    )
    min_spend = models.DecimalField(
        _("Gasto mínimo (€)"),
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    max_uses = models.PositiveIntegerField(
        _("Usos máximos permitidos"),
        default=0,
        help_text=_("0 para usos ilimitados"),
    )
    uses_count = models.PositiveIntegerField(_("Usos canjeados"), default=0)
    valid_from = models.DateTimeField(_("Válido desde"), default=timezone.now)
    valid_until = models.DateTimeField(_("Válido hasta"), null=True, blank=True)
    is_active = models.BooleanField(_("Activo"), default=True)

    class Meta:
        verbose_name = _("Cupón de descuento")
        verbose_name_plural = _("Cupones de descuento")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        unit = "%" if self.discount_type == self.DiscountType.PERCENTAGE else "€"
        return f"{self.code} (-{self.discount_value}{unit})"

    def clean_code(self) -> None:
        self.code = self.code.strip().upper()

    def is_valid(self, subtotal: Decimal) -> tuple[bool, str]:
        """Validate if the coupon can be applied to the current subtotal."""
        now = timezone.now()
        if not self.is_active:
            return False, _("Este cupón no se encuentra activo.")
        if self.valid_from and now < self.valid_from:
            return False, _("Este cupón aún no está disponible.")
        if self.valid_until and now > self.valid_until:
            return False, _("Este cupón ha caducado.")
        if self.max_uses > 0 and self.uses_count >= self.max_uses:
            return False, _("Este cupón ha alcanzado el límite de usos.")
        if subtotal < self.min_spend:
            return False, _("El pedido mínimo para aplicar este cupón es de %(min)s€.") % {"min": self.min_spend}
        return True, ""

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        """Calculate discount amount in EUR (IVA included)."""
        valid, _ = self.is_valid(subtotal)
        if not valid:
            return Decimal("0.00")
        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = subtotal * (self.discount_value / Decimal("100"))
        else:
            discount = self.discount_value
        return min(discount, subtotal).quantize(Decimal("0.01"))


class Cart(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="carts",
        verbose_name=_("Usuario"),
    )
    session_key = models.CharField(
        _("Clave de sesión"),
        max_length=64,
        blank=True,
        db_index=True,
    )
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Cupón aplicado"),
    )
    shipping_method = models.ForeignKey(
        ShippingMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Método de envío seleccionado"),
    )
    shipping_postal_code = models.CharField(
        _("Código Postal"),
        max_length=10,
        blank=True,
        default="28012",
    )

    class Meta:
        verbose_name = _("Carrito de compra")
        verbose_name_plural = _("Carritos de compra")
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        owner = self.user.email if self.user else f"Invitado ({self.session_key[:8]})"
        return f"Carrito #{self.id} de {owner}"

    @property
    def item_count(self) -> int:
        """Number of distinct products in the cart (not total units).

        A tier order of 250 tarjetas is ONE line item, so the header badge,
        drawer and counters read naturally instead of showing "251 artículos".
        """
        return self.items.count()

    @property
    def total_weight_grams(self) -> int:
        return sum(item.product.weight_grams * item.quantity for item in self.items.select_related("product"))

    @property
    def subtotal(self) -> Decimal:
        """Sum of all line items prices (IVA 21% included)."""
        return sum((item.line_total for item in self.items.all()), Decimal("0.00")).quantize(Decimal("0.01"))

    @property
    def discount_amount(self) -> Decimal:
        if not self.coupon:
            return Decimal("0.00")
        return self.coupon.calculate_discount(self.subtotal)

    @property
    def shipping_cost(self) -> Decimal:
        if not self.shipping_method:
            # Default to Madrid Local standard if none selected
            default_method = ShippingMethod.objects.filter(is_active=True).first()
            if default_method:
                return default_method.calculate_cost(self.subtotal, self.total_weight_grams)
            return Decimal("0.00")
        return self.shipping_method.calculate_cost(self.subtotal, self.total_weight_grams)

    @property
    def total(self) -> Decimal:
        """Final total in EUR with IVA 21% included."""
        computed = self.subtotal - self.discount_amount + self.shipping_cost
        return max(Decimal("0.00"), computed).quantize(Decimal("0.01"))

    @property
    def taxable_base(self) -> Decimal:
        """Base imponible sin IVA (total / 1.21)."""
        divisor = Decimal("1.21")
        return (self.total / divisor).quantize(Decimal("0.01"))

    @property
    def iva_amount(self) -> Decimal:
        """Cuota líquida de IVA (21%)."""
        return (self.total - self.taxable_base).quantize(Decimal("0.01"))

    def recalculate(self) -> None:
        """
        Server-side price verification engine.
        Never trust client amounts: recalculate every item against live database models.
        """
        for item in self.items.all():
            item.recalculate_price()
        if self.coupon:
            valid, _ = self.coupon.is_valid(self.subtotal)
            if not valid:
                self.coupon = None
                self.save(update_fields=["coupon"])


class CartItem(TimeStampedModel):
    class ArtworkStatus(models.TextChoices):
        UPLOADED = "uploaded", _("Arte gráfico subido")
        PENDING = "pending", _("Pendiente de enviar")
        PROOF_REQUESTED = "proof_requested", _("Prueba previa solicitada")

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Carrito"),
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="cart_items",
        verbose_name=_("Producto"),
    )
    quantity = models.PositiveIntegerField(_("Cantidad / Tirada"), default=1)
    option_values = models.ManyToManyField(
        ProductOptionValue,
        blank=True,
        related_name="cart_items",
        verbose_name=_("Opciones seleccionadas"),
    )
    selected_options = models.JSONField(
        _("Resumen de opciones"),
        default=dict,
        blank=True,
    )
    artwork_file = models.FileField(
        _("Archivo de diseño subido"),
        upload_to="cart/artwork/%Y/%m/",
        blank=True,
        null=True,
    )
    artwork_status = models.CharField(
        _("Estado del arte"),
        max_length=20,
        choices=ArtworkStatus.choices,
        default=ArtworkStatus.PENDING,
    )
    design_later = models.BooleanField(
        _("Diseñar / enviar más tarde"),
        default=False,
    )
    request_proof = models.BooleanField(
        _("Solicita prueba previa física"),
        default=False,
    )
    proof_price = models.DecimalField(
        _("Coste de prueba física (€)"),
        max_digits=8,
        decimal_places=2,
        default=Decimal("12.00"),
    )
    unit_price = models.DecimalField(
        _("Precio unitario (€)"),
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.00"),
    )
    line_total = models.DecimalField(
        _("Total de línea (€)"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    notes = models.TextField(_("Notas de producción / taller"), blank=True)

    class Meta:
        verbose_name = _("Línea de carrito")
        verbose_name_plural = _("Líneas de carrito")
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.quantity}x {self.product.name} ({self.line_total}€)"

    def recalculate_price(self) -> None:
        """
        Recalculates unit_price and line_total strictly from database records.
        """
        # If product has quantity tiers matching this quantity or lower tier
        tier = self.product.quantity_tiers.filter(min_quantity__lte=self.quantity).order_by("-min_quantity").first()
        if tier:
            base_total = tier.total_price
        else:
            base_total = self.product.base_price * Decimal(self.quantity)

        # Add option modifiers (e.g. Laminado Mate, Stamping Oro, Papel Verjurado)
        options_modifier = sum(
            (ov.price_modifier for ov in self.option_values.all()),
            Decimal("0.00"),
        )

        total = base_total + options_modifier

        if self.request_proof and self.product.allows_proof:
            total += self.proof_price
            self.artwork_status = self.ArtworkStatus.PROOF_REQUESTED
        elif self.artwork_file:
            self.artwork_status = self.ArtworkStatus.UPLOADED
        elif self.design_later:
            self.artwork_status = self.ArtworkStatus.PENDING

        self.line_total = total.quantize(Decimal("0.01"))
        self.unit_price = (self.line_total / Decimal(self.quantity)).quantize(Decimal("0.0001"))
        self.save(update_fields=["unit_price", "line_total", "artwork_status"])
