from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Cart, CartItem, Coupon, ShippingMethod, ShippingZone


class CartItemInline(TabularInline):
    model = CartItem
    extra = 0
    fields = [
        "product",
        "quantity",
        "unit_price",
        "line_total",
        "artwork_status",
        "request_proof",
        "design_later",
    ]
    readonly_fields = ["unit_price", "line_total"]


@admin.register(Cart)
class CartAdmin(ModelAdmin):
    list_display = ["id", "user", "session_key_short", "item_count", "subtotal", "total", "updated_at"]
    list_filter = ["updated_at", "coupon"]
    search_fields = ["user__email", "session_key"]
    inlines = [CartItemInline]
    readonly_fields = ["subtotal", "total", "taxable_base", "iva_amount", "created_at", "updated_at"]

    def session_key_short(self, obj):
        return obj.session_key[:12] + "..." if obj.session_key else "-"

    session_key_short.short_description = "Sesión"


@admin.register(Coupon)
class CouponAdmin(ModelAdmin):
    list_display = [
        "code",
        "discount_type",
        "discount_value",
        "min_spend",
        "uses_count",
        "max_uses",
        "is_active",
        "valid_until",
    ]
    list_filter = ["discount_type", "is_active", "valid_until"]
    search_fields = ["code"]
    list_editable = ["is_active"]


class ShippingMethodInline(TabularInline):
    model = ShippingMethod
    extra = 1
    fields = ["courier", "name", "base_rate", "per_kg_rate", "free_threshold", "estimated_days", "is_active", "order"]


@admin.register(ShippingZone)
class ShippingZoneAdmin(ModelAdmin):
    list_display = ["name", "code", "is_active", "order"]
    list_editable = ["is_active", "order"]
    inlines = [ShippingMethodInline]


@admin.register(ShippingMethod)
class ShippingMethodAdmin(ModelAdmin):
    list_display = [
        "name",
        "zone",
        "courier",
        "base_rate",
        "per_kg_rate",
        "free_threshold",
        "estimated_days",
        "is_active",
    ]
    list_filter = ["zone", "courier", "is_active"]
    list_editable = ["base_rate", "free_threshold", "is_active"]
    search_fields = ["name", "zone__name"]
