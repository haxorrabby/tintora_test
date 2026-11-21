from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """
    Abstract base model providing self-updating created and modified fields.
    """

    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Última modificación"), auto_now=True)

    class Meta:
        abstract = True


class NewsletterSubscriber(TimeStampedModel):
    """GDPR-compliant newsletter opt-in list (double opt-in can be layered on later)."""

    email = models.EmailField(
        _("Correo electrónico"),
        unique=True,
        validators=[EmailValidator()],
    )
    is_active = models.BooleanField(_("Suscrito"), default=True)
    consent_at = models.DateTimeField(_("Fecha de consentimiento"), null=True, blank=True)
    source = models.CharField(_("Origen"), max_length=50, default="footer", blank=True)

    class Meta:
        verbose_name = _("Suscriptor de newsletter")
        verbose_name_plural = _("Suscriptores de newsletter")
        ordering = ["-created_at"]

    def __str__(self):
        return self.email


class Testimonial(TimeStampedModel):
    """Customer testimonial — only published rows render on the homepage."""

    author = models.CharField(_("Nombre y apellidos"), max_length=120)
    role = models.CharField(_("Cargo"), max_length=120, blank=True)
    company = models.CharField(_("Empresa / proyecto"), max_length=160, blank=True)
    quote = models.TextField(_("Testimonio"))
    avatar_initial = models.CharField(_("Inicial del avatar"), max_length=1, blank=True)
    is_published = models.BooleanField(_("Publicado"), default=False)
    order = models.PositiveIntegerField(_("Orden"), default=0)

    class Meta:
        verbose_name = _("Testimonio")
        verbose_name_plural = _("Testimonios")
        ordering = ["order", "-created_at"]

    def __str__(self):
        return f"{self.author} — {self.quote[:40]}…"


class FAQ(TimeStampedModel):
    """Frequently asked question, editable from admin, shown on home + /faq/."""

    class Group(models.TextChoices):
        PEDIDOS = "pedidos", _("Pedidos")
        IMPRESION = "impresion", _("Impresión")
        ENVIOS = "envios", _("Envíos")
        DISENOS = "disenos", _("Diseños")
        PAGOS = "pagos", _("Pagos")
        DEVOLUCIONES = "devoluciones", _("Devoluciones")

    group = models.CharField(
        _("Grupo"),
        max_length=20,
        choices=Group.choices,
        default=Group.PEDIDOS,
    )
    question = models.CharField(_("Pregunta"), max_length=300)
    answer = models.TextField(_("Respuesta"))
    is_published = models.BooleanField(_("Publicada"), default=True)
    order = models.PositiveIntegerField(_("Orden"), default=0)

    class Meta:
        verbose_name = _("Pregunta frecuente")
        verbose_name_plural = _("Preguntas frecuentes")
        ordering = ["order", "id"]

    def __str__(self):
        return self.question


class HomepageSettings(TimeStampedModel):
    """
    Singleton (pk=1) with all admin-managed homepage copy: announcement bar,
    hero copy/CTAs, promotional campaign banner and newsletter block copy.
    """

    # Announcement bar
    announcement_enabled = models.BooleanField(_("Barra de anuncio activa"), default=True)
    announcement_text = models.CharField(
        _("Texto del anuncio"),
        max_length=200,
        default="Envíos a toda España · Producción rápida en Madrid",
    )
    announcement_link_label = models.CharField(
        _("Etiqueta del enlace del anuncio"), max_length=60, blank=True, default="Envío gratis desde 75 €"
    )
    announcement_link = models.CharField(
        _("URL del enlace del anuncio"),
        max_length=300,
        blank=True,
        default="/catalogo/",
        help_text=_("Ruta relativa o URL absoluta. Vacío = sin enlace."),
    )

    # Hero
    hero_eyebrow = models.CharField(
        _("Hero: antetítulo"),
        max_length=120,
        default="IMPRESIÓN · DISEÑO · PRODUCTOS PERSONALIZADOS",
    )
    hero_title = models.CharField(_("Hero: titular"), max_length=160, default="Todo lo que imaginas. Lo imprimimos.")
    hero_subtitle = models.CharField(
        _("Hero: texto de apoyo"),
        max_length=300,
        default="Productos personalizados, impresión profesional y soluciones digitales desde Madrid.",
    )
    hero_primary_label = models.CharField(_("Hero: CTA primaria"), max_length=60, default="Comprar ahora")
    hero_primary_url = models.CharField(_("Hero: CTA primaria URL"), max_length=300, default="/catalogo/")
    hero_secondary_label = models.CharField(_("Hero: CTA secundaria"), max_length=60, default="Ver servicios")
    hero_secondary_url = models.CharField(_("Hero: CTA secundaria URL"), max_length=300, default="/contacto/")

    # Promotional campaign banner
    promo_enabled = models.BooleanField(_("Banner promocional activo"), default=False)
    promo_title = models.CharField(_("Promo: titular"), max_length=160, blank=True, default="10 % de descuento en tu primer pedido")
    promo_text = models.CharField(
        _("Promo: texto"),
        max_length=300,
        blank=True,
        default="Usa el código de bienvenida en el carrito. Válido para el primer pedido.",
    )
    promo_cta_label = models.CharField(_("Promo: etiqueta CTA"), max_length=60, blank=True, default="Descubrir oferta")
    promo_cta_url = models.CharField(_("Promo: URL CTA"), max_length=300, blank=True, default="/catalogo/")

    # Newsletter block copy
    newsletter_title = models.CharField(
        _("Newsletter: titular"), max_length=140, default="Recibe novedades, ofertas y nuevos productos."
    )
    newsletter_text = models.CharField(
        _("Newsletter: texto"),
        max_length=240,
        blank=True,
        default="Sin spam. Solo lanzamientos, guías de impresión y ofertas puntuales.",
    )

    class Meta:
        verbose_name = _("Contenido de la portada")
        verbose_name_plural = _("Contenido de la portada")

    def __str__(self):
        return str(_("Contenido de la portada"))

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        from django.core.cache import cache  # noqa: PLC0415

        cache.delete("homepage_settings")

    def delete(self, *args, **kwargs):  # pragma: no cover - singleton guard
        raise ValidationError(_("El singleton de portada no se puede eliminar."))

    @classmethod
    def get_solo(cls) -> "HomepageSettings":
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    def get_cached(cls) -> "HomepageSettings":
        """Cached singleton for global contexts (announcement bar, footer copy).

        Cleared automatically after the TTL; edit + save invalidates immediately.
        """
        from django.core.cache import cache  # noqa: PLC0415

        cached = cache.get("homepage_settings")
        if cached is not None:
            return cached
        obj = cls.get_solo()
        cache.set("homepage_settings", obj, 300)
        return obj


class PortfolioItem(TimeStampedModel):
    """Admin-managed showcase of real work photographs.

    The home page portfolio section renders only published items — with an
    empty list the section is hidden entirely, so no placeholder or invented
    work is ever shown.
    """

    title = models.CharField(_("Título"), max_length=140)
    description = models.CharField(
        _("Descripción corta"),
        max_length=240,
        blank=True,
        help_text=_("Ej. Tarjetas con stamping en oro · 400 g/m²"),
    )
    image = models.ImageField(_("Fotografía del trabajo"), upload_to="portfolio/%Y/%m/")
    alt_text = models.CharField(
        _("Texto alternativo"),
        max_length=200,
        blank=True,
        help_text=_("Descripción accesible de la fotografía (para lectores de pantalla)."),
    )
    area = models.CharField(
        _("Área"),
        max_length=20,
        blank=True,
        choices=[
            ("impresion", "Impresión"),
            ("sublimacion", "Sublimación"),
            ("latinos", "Latino"),
            ("web", "Web"),
        ],
    )
    order = models.PositiveIntegerField(_("Orden"), default=0)
    is_published = models.BooleanField(_("Publicado"), default=True)

    class Meta:
        verbose_name = "Trabajo del portafolio"
        verbose_name_plural = "Portafolio (fotos reales)"
        ordering = ["order", "created_at"]

    def __str__(self):
        return self.title
