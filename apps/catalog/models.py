import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class BusinessArea(models.TextChoices):
    IMPRESION = "impresion", _("01. Impresión")
    SUBLIMACION = "sublimacion", _("02. Sublimación")
    LATINOS = "latinos", _("03. Productos Latinos")
    WEB = "web", _("04. Desarrollo Web")


class Category(TimeStampedModel):
    name = models.CharField(_("Nombre de la categoría"), max_length=150)
    slug = models.SlugField(_("Slug / URL"), max_length=160, unique=True)
    business_area = models.CharField(
        _("Área de negocio"),
        max_length=20,
        choices=BusinessArea.choices,
        default=BusinessArea.IMPRESION,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("Categoría superior (opcional)"),
    )
    description = models.TextField(_("Descripción editorial"), blank=True)
    image = models.ImageField(_("Imagen de portada"), upload_to="catalog/categories/", blank=True, null=True)
    order = models.PositiveIntegerField(_("Orden de visualización"), default=0)
    is_active = models.BooleanField(_("Activa"), default=True)

    class Meta:
        verbose_name = _("Categoría")
        verbose_name_plural = _("Categorías")
        ordering = ["business_area", "order", "name"]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return f"[{self.get_business_area_display()}] {self.name}"

    def get_absolute_url(self) -> str:
        return reverse("catalog:category_detail", kwargs={"slug": self.slug})


class Brand(TimeStampedModel):
    """Product brand (e.g. Oriental, Pony Malta, Tesoro Natural).

    Brands are only created when a catalog explicitly names them; the admin
    can create and assign any other brand through Django Admin.
    """

    name = models.CharField(_("Nombre de la marca"), max_length=120, unique=True)
    slug = models.SlugField(_("Slug / URL"), max_length=140, unique=True)

    class Meta:
        verbose_name = _("Marca")
        verbose_name_plural = _("Marcas")
        ordering = ["name"]

    def __str__(self):
        return self.name


_VARIANT_SIZE_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(kg|g|gr|ml|l|cl|oz|lb)\.?\s*$", re.I)
_VARIANT_UNIT_FACTORS = {
    "kg": ("weight", Decimal("1000")),
    "g": ("weight", Decimal("1")),
    "gr": ("weight", Decimal("1")),
    "lb": ("weight", Decimal("453.59237")),
    "oz": ("weight", Decimal("28.349523125")),
    "l": ("volume", Decimal("1000")),
    "cl": ("volume", Decimal("10")),
    "ml": ("volume", Decimal("1")),
}


def _variant_sort_key(label: str) -> tuple[str, Decimal, str]:
    match = _VARIANT_SIZE_RE.fullmatch(label or "")
    if not match:
        return ("other", Decimal("0"), (label or "").casefold())
    amount = Decimal(match.group(1).replace(",", "."))
    dimension, factor = _VARIANT_UNIT_FACTORS[match.group(2).casefold()]
    return (dimension, amount * factor, label.casefold())


class Product(TimeStampedModel):
    class ImageReviewStatus(models.TextChoices):
        PENDING = "pending", _("Pendiente de revisión")
        VERIFIED = "verified", _("Verificada")
        MANUAL_REVIEW = "manual_review", _("Revisión manual necesaria")

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name=_("Categoría"),
    )
    business_area = models.CharField(
        _("Área de negocio"),
        max_length=20,
        choices=BusinessArea.choices,
        default=BusinessArea.IMPRESION,
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        verbose_name=_("Marca"),
    )
    parent_product = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="size_variants",
        verbose_name=_("Producto principal"),
        help_text=_("Dejar vacío para un producto principal; seleccionar el producto principal para una variante."),
    )
    variant_label = models.CharField(
        _("Tamaño / variante"),
        max_length=80,
        blank=True,
        help_text=_("Ej. 250 g, 500 ml o 1 kg. Cada variante conserva su precio y stock."),
    )
    name = models.CharField(_("Nombre del producto"), max_length=200)
    slug = models.SlugField(_("Slug / URL"), max_length=220, unique=True)
    sku = models.CharField(_("Referencia / SKU"), max_length=50, unique=True, blank=True, null=True)
    short_description = models.CharField(_("Resumen editorial corto"), max_length=300)
    description = models.TextField(_("Descripción completa & Especificaciones"))

    # Pricing & Fiscal (Spain IVA 21%)
    base_price = models.DecimalField(
        _("Precio base (€)"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("Precio en Euros con IVA 21% incluido"),
    )
    iva_percentage = models.DecimalField(
        _("IVA aplicable (%)"),
        max_digits=4,
        decimal_places=1,
        default=Decimal("21.0"),
    )

    # Visibility & Status
    is_active = models.BooleanField(_("Publicado / Activo"), default=True)
    is_featured = models.BooleanField(_("Destacado en Portada"), default=False)

    # Print / Sublimation Configurator Flags
    is_configurable = models.BooleanField(
        _("Configurable en vivo"),
        default=False,
        help_text=_("Habilita el configurador interactivo con opciones de papel, tamaños y escalado por volumen"),
    )
    allows_file_upload = models.BooleanField(
        _("Permite subir arte gráfico"),
        default=False,
        help_text=_("Habilita carga y validación de archivos PDF/AI/PSD/SVG"),
    )
    allows_proof = models.BooleanField(
        _("Permite solicitar prueba previa"),
        default=False,
        help_text=_('Ofrece opción de "Pide una prueba digital o física" antes de tirada completa'),
    )
    turnaround_days = models.PositiveIntegerField(
        _("Plazo de producción (días hábiles)"),
        default=2,
        help_text=_("Tiempo de taller en Madrid antes de expedición"),
    )

    # Physical / Retail Attributes (Latin grocery & physical stock)
    weight_grams = models.PositiveIntegerField(
        _("Peso neto (gramos)"),
        default=0,
        help_text=_("Necesario para el cálculo de tarifas de envío por peso"),
    )
    origin_country = models.CharField(
        _("País de origen"),
        max_length=100,
        blank=True,
        help_text=_("Ej. Colombia, México, Venezuela, Perú, España"),
    )
    stock = models.IntegerField(_("Unidades en stock"), default=100)
    low_stock_threshold = models.IntegerField(_("Alerta de stock bajo"), default=10)
    image_review_status = models.CharField(
        _("Estado de revisión de imagen"),
        max_length=20,
        choices=ImageReviewStatus.choices,
        default=ImageReviewStatus.PENDING,
    )
    image_review_notes = models.CharField(_("Notas de revisión de imagen"), max_length=255, blank=True)

    # SEO & Search Engine Optimization
    meta_title = models.CharField(_("Título SEO"), max_length=150, blank=True)
    meta_description = models.CharField(_("Descripción SEO"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("Producto")
        verbose_name_plural = _("Productos")
        ordering = ["business_area", "-is_featured", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["parent_product", "variant_label"],
                condition=Q(parent_product__isnull=False),
                name="unique_size_variant_label_per_parent",
            )
        ]

    def __str__(self):
        return f"{self.display_name}{f' · {self.variant_label}' if self.variant_label else ''}"

    def get_absolute_url(self) -> str:
        return reverse("catalog:product_detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        # Synchronize business_area with category if not specified
        if self.category and not self.business_area:
            self.business_area = self.category.business_area
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.parent_product_id:
            if self.parent_product_id == self.pk:
                raise ValidationError({"parent_product": _("Un producto no puede ser variante de sí mismo.")})
            if self.parent_product.parent_product_id:
                raise ValidationError({"parent_product": _("Las variantes solo pueden tener un nivel.")})
            if self.category_id != self.parent_product.category_id:
                raise ValidationError({"category": _("La variante debe pertenecer a la categoría del producto principal.")})
            if self.business_area != self.parent_product.business_area or self.brand_id != self.parent_product.brand_id:
                raise ValidationError(
                    _("La variante debe compartir el área comercial y la marca del producto principal.")
                )
            if not self.variant_label.strip():
                raise ValidationError({"variant_label": _("Indica el tamaño o nombre de esta variante.")})

    @property
    def display_name(self) -> str:
        return self.parent_product.name if self.parent_product_id else self.name

    @property
    def variant_root(self):
        return self.parent_product or self

    @property
    def active_variants(self):
        root = self.variant_root
        prefetched = getattr(root, "_prefetched_objects_cache", {}).get("size_variants")
        children = (
            [variant for variant in prefetched if variant.is_active]
            if prefetched is not None
            else list(root.size_variants.filter(is_active=True))
        )
        variants = [root, *children]
        return sorted(variants, key=lambda variant: _variant_sort_key(variant.variant_label))

    @property
    def has_size_variants(self) -> bool:
        root = self.variant_root
        prefetched = getattr(root, "_prefetched_objects_cache", {}).get("size_variants")
        if prefetched is not None:
            return any(variant.is_active for variant in prefetched)
        return root.size_variants.filter(is_active=True).exists()

    @property
    def tracks_inventory(self) -> bool:
        return (
            self.business_area == BusinessArea.LATINOS
            or self.parent_product_id is not None
            or self.has_size_variants
        )

    @property
    def has_product_image(self) -> bool:
        return "tintora-logo-mono.svg" not in self.primary_image_url

    @property
    def price_without_iva(self) -> Decimal:
        divisor = Decimal(1) + (self.iva_percentage / Decimal(100))
        return (self.base_price / divisor).quantize(Decimal("0.01"))

    @property
    def iva_amount(self) -> Decimal:
        return (self.base_price - self.price_without_iva).quantize(Decimal("0.01"))

    @property
    def in_stock(self) -> bool:
        return self.stock > 0

    @property
    def is_low_stock(self) -> bool:
        return self.stock <= self.low_stock_threshold

    @property
    def primary_image_url(self) -> str:
        prefetched_images = getattr(self, "_prefetched_objects_cache", {}).get("images")
        if prefetched_images is None:
            primary = self.images.filter(is_primary=True).first() or self.images.first()
        else:
            primary = next((image for image in prefetched_images if image.is_primary), None)
            primary = primary or (prefetched_images[0] if prefetched_images else None)
        if primary:
            return primary.get_url()
        if self.parent_product_id:
            return self.parent_product.primary_image_url
        prefetched_variants = getattr(self, "_prefetched_objects_cache", {}).get("size_variants")
        variants = (
            [variant for variant in prefetched_variants if variant.is_active]
            if prefetched_variants is not None
            else list(self.size_variants.filter(is_active=True))
        )
        for variant in variants:
            images = list(variant.images.all())
            for image in images:
                if image.is_primary:
                    return image.get_url()
            if images:
                return images[0].get_url()
        return "/static/images/brand/tintora-logo-mono.svg"

    @property
    def is_quick_addable(self) -> bool:
        """True when the product can go straight into the cart from a card.

        Configurable products expose required option groups through the live
        configurator (option groups are only defined on configurable
        products), so they always route to the detail page instead.
        """
        return not self.is_configurable


class ProductImage(TimeStampedModel):
    class VerificationStatus(models.TextChoices):
        PENDING = "pending", _("Pendiente de verificación")
        VERIFIED = "verified", _("Verificada")
        MANUAL_REVIEW = "manual_review", _("Revisión manual necesaria")

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name=_("Producto"),
    )
    image = models.ImageField(_("Archivo de imagen"), upload_to="catalog/products/%Y/%m/", blank=True, null=True)
    image_url = models.CharField(
        _("URL externa / estática de respaldo"),
        max_length=500,
        blank=True,
        help_text=_("Si se deja vacía se usa el archivo subido"),
    )
    source_url = models.URLField(_("Fuente de la imagen"), blank=True)
    license_note = models.CharField(_("Permiso / licencia"), max_length=255, blank=True)
    verification_status = models.CharField(
        _("Verificación de imagen"),
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    alt_text = models.CharField(_("Texto alternativo (accesibilidad y SEO)"), max_length=200, blank=True)
    is_primary = models.BooleanField(_("Imagen principal"), default=False)
    order = models.PositiveIntegerField(_("Orden"), default=0)

    class Meta:
        verbose_name = _("Imagen de producto")
        verbose_name_plural = _("Imágenes de producto")
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"Imagen #{self.id} de {self.product.name}"

    def clean(self):
        super().clean()
        if self.verification_status == self.VerificationStatus.VERIFIED:
            errors = {}
            if not self.source_url:
                errors["source_url"] = _("Añade la fuente antes de verificar la imagen.")
            if not self.license_note:
                errors["license_note"] = _("Indica el permiso o licencia de uso antes de verificar la imagen.")
            if not self.image and not self.image_url:
                errors["image"] = _("Asigna un archivo o una URL de imagen antes de verificarla.")
            if errors:
                raise ValidationError(errors)

    def get_url(self) -> str:
        if self.image:
            return self.image.url
        if self.image_url:
            return self.image_url
        return "/static/images/brand/tintora-logo-mono.svg"


class ProductOptionGroup(TimeStampedModel):
    """
    Groups of options for configurators (e.g. 'Tamaño', 'Papel', 'Acabado', 'Caras')
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="option_groups",
        verbose_name=_("Producto"),
    )
    name = models.CharField(_("Nombre de la opción"), max_length=100)
    code = models.SlugField(_("Identificador técnico"), max_length=50, help_text=_("Ej. tamano, papel, caras, acabado"))
    is_required = models.BooleanField(_("Obligatorio"), default=True)
    order = models.PositiveIntegerField(_("Orden"), default=0)

    class Meta:
        verbose_name = _("Grupo de opciones de producto")
        verbose_name_plural = _("Grupos de opciones de producto")
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.product.name} — {self.name}"


class ProductOptionValue(TimeStampedModel):
    """
    Individual selectable values within an option group.
    """

    group = models.ForeignKey(
        ProductOptionGroup,
        on_delete=models.CASCADE,
        related_name="values",
        verbose_name=_("Grupo de opción"),
    )
    name = models.CharField(_("Valor"), max_length=150)
    price_modifier = models.DecimalField(
        _("Suplemento sobre precio base (€)"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("Importe adicional con IVA incluido"),
    )
    is_default = models.BooleanField(_("Seleccionado por defecto"), default=False)
    order = models.PositiveIntegerField(_("Orden"), default=0)

    class Meta:
        verbose_name = _("Valor de opción")
        verbose_name_plural = _("Valores de opción")
        ordering = ["order", "name"]

    def __str__(self):
        modifier_str = f" (+{self.price_modifier}€)" if self.price_modifier > 0 else ""
        return f"{self.group.name}: {self.name}{modifier_str}"


class QuantityTierPrice(TimeStampedModel):
    """
    Volume tier pricing table (escalado de precios por cantidad).
    Essential for printing & sublimation studios.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="quantity_tiers",
        verbose_name=_("Producto"),
    )
    min_quantity = models.PositiveIntegerField(_("Cantidad de unidades"), help_text=_("Ej. 50, 100, 250, 500, 1000"))
    unit_price = models.DecimalField(
        _("Precio unitario (€/ud)"),
        max_digits=10,
        decimal_places=4,
        help_text=_("Precio por unidad con IVA incluido para este tramo"),
    )
    total_price = models.DecimalField(
        _("Precio total del tramo (€)"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Precio cerrado total con IVA incluido"),
    )
    order = models.PositiveIntegerField(_("Orden"), default=0)

    class Meta:
        verbose_name = _("Tramo de precio por cantidad")
        verbose_name_plural = _("Tramos de precios por cantidad")
        ordering = ["min_quantity"]

    def __str__(self):
        return f"{self.product.name}: {self.min_quantity} uds → {self.total_price}€ ({self.unit_price}€/ud)"
