from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import CustomUser, SavedAddress, Wishlist


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin, ModelAdmin):
    list_display = (
        "email",
        "display_name",
        "customer_type_badge",
        "nif_cif",
        "phone",
        "city",
        "is_verified",
        "is_staff",
    )
    list_filter = ("customer_type", "is_verified", "is_staff", "is_superuser", "city")
    search_fields = ("email", "first_name", "last_name", "company_name", "nif_cif", "phone")
    ordering = ("-created_at",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Información Personal / Empresa"),
            {
                "fields": (
                    "customer_type",
                    "company_name",
                    "nif_cif",
                    "first_name",
                    "last_name",
                    "phone",
                )
            },
        ),
        (
            _("Dirección de Facturación & Envío"),
            {
                "fields": (
                    "address",
                    "postal_code",
                    "city",
                    "province",
                    "country",
                )
            },
        ),
        (
            _("Preferencias & Seguridad"),
            {
                "fields": (
                    "is_verified",
                    "totp_enabled",
                    "newsletter_subscribed",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Fechas Importantes"), {"fields": ("last_login", "date_joined")}),
    )
    readonly_fields = ("totp_enabled",)

    @display(description=_("Nombre / Razón Social"))
    def display_name(self, obj):
        if obj.customer_type == CustomUser.CustomerType.BUSINESS and obj.company_name:
            return obj.company_name
        return obj.get_full_name() or "-"

    @display(
        description=_("Tipo"),
        label={
            CustomUser.CustomerType.INDIVIDUAL: "info",
            CustomUser.CustomerType.BUSINESS: "success",
        },
    )
    def customer_type_badge(self, obj):
        return obj.get_customer_type_display()


@admin.register(SavedAddress)
class SavedAddressAdmin(ModelAdmin):
    list_display = ("label", "user", "city", "is_default", "created_at")
    list_filter = ("is_default", "country", "province")
    search_fields = ("label", "address_line1", "city", "user__email")
    ordering = ("-is_default", "label")


@admin.register(Wishlist)
class WishlistAdmin(ModelAdmin):
    list_display = ("user", "product", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__email", "product__name")
    ordering = ("-created_at",)
