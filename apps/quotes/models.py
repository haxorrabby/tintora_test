from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class WebPackage(TimeStampedModel):
    name = models.CharField(_("Nombre del paquete"), max_length=150)
    slug = models.SlugField(_("Slug / URL"), max_length=160, unique=True)
    starting_price = models.DecimalField(
        _("Precio desde (€)"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("490.00"),
    )
    price_display = models.CharField(
        _("Texto comercial del precio"),
        max_length=100,
        default="desde 490€",
        help_text=_("Ej. desde 490€ (+ IVA) o Consultar a medida"),
    )
    delivery_timeline = models.CharField(
        _("Plazo estimado de entrega"),
        max_length=100,
        default="5 - 7 días hábiles",
    )
    short_summary = models.CharField(_("Resumen editorial"), max_length=255)
    features = models.JSONField(
        _("Lista de características incluidas"),
        default=list,
        help_text=_("Lista JSON con las ventajas del paquete"),
    )
    is_featured = models.BooleanField(_("Paquete destacado / Más popular"), default=False)
    order = models.PositiveIntegerField(_("Orden"), default=0)
    is_active = models.BooleanField(_("Activo en la web"), default=True)

    class Meta:
        verbose_name = _("Paquete de Desarrollo Web")
        verbose_name_plural = _("Paquetes de Desarrollo Web")
        ordering = ["order", "starting_price"]

    def __str__(self):
        return f"{self.name} ({self.price_display})"


class WebPortfolioProject(TimeStampedModel):
    title = models.CharField(_("Título del proyecto"), max_length=150)
    slug = models.SlugField(_("Slug / URL"), max_length=170, unique=True)
    client_name = models.CharField(_("Cliente / marca"), max_length=150, blank=True)
    sector = models.CharField(_("Sector"), max_length=100, blank=True)
    summary = models.CharField(_("Resumen del caso"), max_length=300)
    image = models.ImageField(_("Imagen del proyecto"), upload_to="web-portfolio/%Y/%m/", blank=True)
    project_url = models.URLField(_("URL pública"), blank=True)
    technologies = models.JSONField(_("Tecnologías"), default=list, blank=True)
    order = models.PositiveIntegerField(_("Orden"), default=0)
    is_featured = models.BooleanField(_("Destacado"), default=False)
    is_active = models.BooleanField(_("Visible en la web"), default=True)

    class Meta:
        verbose_name = _("Proyecto de portfolio web")
        verbose_name_plural = _("Portfolio de Desarrollo Web")
        ordering = ["-is_featured", "order", "title"]

    def __str__(self):
        return self.title


class QuoteRequest(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "nuevo", _("Nuevo Lead")
        CONTACTED = "contactado", _("Contactado por Asesor")
        IN_STUDY = "en_estudio", _("En Estudio Técnico")
        PROPOSAL_SENT = "presupuesto_enviado", _("Presupuesto Enviado")
        WON = "ganado", _("Ganado / Proyecto en Marcha")
        ARCHIVED = "archivado", _("Archivado / Descartado")

    class ServiceType(models.TextChoices):
        WEB = "web", _("Desarrollo Web & IT")
        PRINT = "impresion", _("Impresión a Medida / Gran Tirada")
        SUBLIMATION = "sublimacion", _("Merchandising / Sublimación Corporativa")
        MIXED = "mixto", _("Proyecto Integral Marca + Web + Papelería")

    service_type = models.CharField(
        _("Tipo de servicio"),
        max_length=30,
        choices=ServiceType.choices,
        default=ServiceType.WEB,
    )
    package = models.ForeignKey(
        WebPackage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
        verbose_name=_("Paquete de interés"),
    )
    full_name = models.CharField(_("Nombre y apellidos"), max_length=150)
    company_name = models.CharField(_("Empresa / Marca"), max_length=150, blank=True)
    email = models.EmailField(_("Correo electrónico de contacto"))
    phone = models.CharField(_("Teléfono / WhatsApp"), max_length=40)
    nif_cif = models.CharField(_("NIF / CIF (opcional)"), max_length=30, blank=True)
    budget_range = models.CharField(
        _("Rango de presupuesto aproximado"),
        max_length=60,
        blank=True,
        default="1.000€ - 3.000€",
    )
    project_description = models.TextField(_("Descripción del proyecto / requerimientos"))
    attachment = models.FileField(
        _("Archivo adjunto / Briefing"),
        upload_to="quotes/briefs/%Y/%m/",
        blank=True,
        null=True,
    )
    status = models.CharField(
        _("Estado del lead"),
        max_length=30,
        choices=Status.choices,
        default=Status.NEW,
    )
    internal_notes = models.TextField(
        _("Notas internas del equipo de producción"),
        blank=True,
    )

    class Meta:
        verbose_name = _("Solicitud de Presupuesto (Lead)")
        verbose_name_plural = _("Solicitudes de Presupuesto (Leads)")
        ordering = ["-created_at"]

    def __str__(self):
        empresa = f" ({self.company_name})" if self.company_name else ""
        return f"{self.full_name}{empresa} - {self.get_service_type_display()} [{self.get_status_display()}]"
