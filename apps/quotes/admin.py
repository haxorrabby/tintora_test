from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import QuoteRequest, WebPackage, WebPortfolioProject


@admin.register(WebPackage)
class WebPackageAdmin(ModelAdmin):
    list_display = ("name", "price_display", "delivery_timeline", "is_featured", "order", "is_active")
    list_filter = ("is_featured", "is_active")
    search_fields = ("name", "short_summary")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("order", "starting_price")


@admin.register(WebPortfolioProject)
class WebPortfolioProjectAdmin(ModelAdmin):
    list_display = ("title", "client_name", "sector", "is_featured", "order", "is_active")
    list_filter = ("is_featured", "is_active", "sector")
    search_fields = ("title", "client_name", "sector", "summary")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("-is_featured", "order", "title")
    fieldsets = (
        (_("Proyecto"), {"fields": ("title", "slug", "client_name", "sector", "summary", "image", "project_url")}),
        (_("Tecnología y publicación"), {"fields": ("technologies", "order", "is_featured", "is_active")}),
    )


@admin.register(QuoteRequest)
class QuoteRequestAdmin(ModelAdmin):
    list_display = (
        "full_name",
        "company_name",
        "service_type_badge",
        "package",
        "budget_range",
        "status_badge",
        "created_at",
    )
    list_filter = ("service_type", "status", "created_at")
    search_fields = ("full_name", "company_name", "email", "phone", "project_description", "nif_cif")
    ordering = ("-created_at",)

    fieldsets = (
        (
            _("Datos del Contacto & Empresa"),
            {
                "fields": (
                    "full_name",
                    "company_name",
                    "email",
                    "phone",
                    "nif_cif",
                )
            },
        ),
        (
            _("Detalles del Proyecto"),
            {
                "fields": (
                    "service_type",
                    "package",
                    "budget_range",
                    "project_description",
                    "attachment",
                )
            },
        ),
        (
            _("Seguimiento Comercial & Estado"),
            {
                "fields": (
                    "status",
                    "internal_notes",
                )
            },
        ),
    )

    @display(
        description=_("Servicio"),
        label={
            QuoteRequest.ServiceType.WEB: "primary",
            QuoteRequest.ServiceType.PRINT: "danger",
            QuoteRequest.ServiceType.SUBLIMATION: "warning",
            QuoteRequest.ServiceType.MIXED: "info",
        },
    )
    def service_type_badge(self, obj):
        return obj.get_service_type_display()

    @display(
        description=_("Estado del Lead"),
        label={
            QuoteRequest.Status.NEW: "danger",
            QuoteRequest.Status.CONTACTED: "warning",
            QuoteRequest.Status.IN_STUDY: "info",
            QuoteRequest.Status.PROPOSAL_SENT: "primary",
            QuoteRequest.Status.WON: "success",
            QuoteRequest.Status.ARCHIVED: "secondary",
        },
    )
    def status_badge(self, obj):
        return obj.get_status_display()
