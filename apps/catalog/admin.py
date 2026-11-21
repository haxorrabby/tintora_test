from django import forms
from django.contrib import admin
from django.forms.models import BaseInlineFormSet
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from .models import (
    Brand,
    BusinessArea,
    Category,
    Product,
    ProductImage,
    ProductOptionGroup,
    ProductOptionValue,
    QuantityTierPrice,
)


class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 1
    fields = (
        "image",
        "image_url",
        "source_url",
        "license_note",
        "verification_status",
        "alt_text",
        "is_primary",
        "order",
    )


class QuantityTierPriceInline(TabularInline):
    model = QuantityTierPrice
    extra = 2
    fields = ("min_quantity", "unit_price", "total_price", "order")


class ProductOptionValueInline(TabularInline):
    model = ProductOptionValue
    extra = 2
    fields = ("name", "price_modifier", "is_default", "order")


class ProductVariantInlineForm(forms.ModelForm):
    variant_label = forms.CharField(required=True)

    class Meta:
        model = Product
        fields = ("variant_label", "base_price", "stock", "weight_grams", "is_active", "image_review_status")


class ProductVariantInlineFormSet(BaseInlineFormSet):
    def _construct_form(self, index, **kwargs):
        form = super()._construct_form(index, **kwargs)
        if not form.instance.pk:
            form.instance.parent_product = self.instance
            form.instance.category = self.instance.category
            form.instance.business_area = self.instance.business_area
            form.instance.brand = self.instance.brand
            form.instance.name = self.instance.name
            form.instance.short_description = self.instance.short_description
            form.instance.description = self.instance.description
        return form

    def save_new(self, form, commit=True):
        instance = form.save(commit=False)
        parent = self.instance
        instance.parent_product = parent
        instance.category = parent.category
        instance.business_area = parent.business_area
        instance.brand = parent.brand
        instance.name = parent.name
        instance.short_description = parent.short_description
        instance.description = parent.description
        base_slug = slugify(f"{parent.slug}-{instance.variant_label}")[:210] or parent.slug
        candidate = base_slug
        suffix = 2
        while Product.objects.filter(slug=candidate).exists():
            candidate = f"{base_slug[:205]}-{suffix}"
            suffix += 1
        instance.slug = candidate
        instance.sku = None
        if commit:
            instance.save()
            form.save_m2m()
        return instance


class ProductVariantInline(TabularInline):
    model = Product
    fk_name = "parent_product"
    form = ProductVariantInlineForm
    formset = ProductVariantInlineFormSet
    extra = 0
    fields = ("variant_label", "base_price", "stock", "weight_grams", "is_active", "image_review_status")
    verbose_name = _("Tamaño / variante")
    verbose_name_plural = _("Tamaños y variantes (precio y stock independientes)")


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("name", "area_badge", "parent", "order", "is_active")
    list_filter = ("business_area", "is_active")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("business_area", "order", "name")

    @display(
        description=_("Área Comercial"),
        label={
            BusinessArea.IMPRESION: "danger",
            BusinessArea.SUBLIMACION: "warning",
            BusinessArea.LATINOS: "info",
            BusinessArea.WEB: "primary",
        },
    )
    def area_badge(self, obj):
        return obj.get_business_area_display()


@admin.register(Brand)
class BrandAdmin(ModelAdmin):
    list_display = ("name", "product_count", "created_at")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)

    @display(description=_("Productos"))
    def product_count(self, obj):
        return obj.products.count()


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = (
        "name",
        "variant_label",
        "parent_product",
        "brand",
        "area_badge",
        "category",
        "origin_country",
        "base_price",
        "stock_display",
        "image_review_status",
        "is_configurable",
        "is_featured",
        "is_active",
    )
    list_filter = (
        "business_area",
        "category",
        "brand",
        "is_active",
        "is_featured",
        "is_configurable",
        "allows_file_upload",
        "image_review_status",
    )
    search_fields = ("name", "variant_label", "short_description", "description", "origin_country", "brand__name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline, QuantityTierPriceInline, ProductVariantInline]

    def get_inlines(self, request, obj=None):
        if obj and obj.parent_product_id:
            return (ProductImageInline, QuantityTierPriceInline)
        return super().get_inlines(request, obj)

    fieldsets = (
        (
            _("Información Básica"),
            {
                "fields": (
                    "business_area",
                    "category",
                    "brand",
                    "parent_product",
                    "name",
                    "slug",
                    "variant_label",
                    "short_description",
                    "description",
                )
            },
        ),
        (
            _("Tarifas e Impuestos (España)"),
            {
                "fields": (
                    "base_price",
                    "iva_percentage",
                )
            },
        ),
        (
            _("Opciones de Configuración e Imprenta"),
            {
                "fields": (
                    "is_configurable",
                    "allows_file_upload",
                    "allows_proof",
                    "turnaround_days",
                )
            },
        ),
        (
            _("Logística & Stock (Productos Latinos y Merch)"),
            {
                "fields": (
                    "weight_grams",
                    "origin_country",
                    "stock",
                    "low_stock_threshold",
                )
            },
        ),
        (
            _("Revisión de imágenes"),
            {"fields": ("image_review_status", "image_review_notes")},
        ),
        (
            _("Visibilidad & SEO"),
            {
                "fields": (
                    "is_active",
                    "is_featured",
                    "meta_title",
                    "meta_description",
                )
            },
        ),
    )

    @display(
        description=_("Área"),
        label={
            BusinessArea.IMPRESION: "danger",
            BusinessArea.SUBLIMACION: "warning",
            BusinessArea.LATINOS: "info",
            BusinessArea.WEB: "primary",
        },
    )
    def area_badge(self, obj):
        return obj.get_business_area_display()

    @display(
        description=_("Stock / Estado"),
        label=lambda obj: (
            "success" if obj.stock > obj.low_stock_threshold else ("warning" if obj.stock > 0 else "danger")
        ),
    )
    def stock_display(self, obj):
        if obj.business_area in [BusinessArea.IMPRESION, BusinessArea.SUBLIMACION]:
            return "Bajo Demanda"
        return f"{obj.stock} uds"


@admin.register(ProductOptionGroup)
class ProductOptionGroupAdmin(ModelAdmin):
    list_display = ("name", "product", "code", "is_required", "order")
    list_filter = ("product__business_area", "is_required")
    search_fields = ("name", "product__name", "code")
    inlines = [ProductOptionValueInline]


@admin.register(ProductOptionValue)
class ProductOptionValueAdmin(ModelAdmin):
    list_display = ("name", "group", "price_modifier", "is_default", "order")
    list_filter = ("group__product__business_area", "is_default")
    search_fields = ("name", "group__name")
