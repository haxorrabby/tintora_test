from django.contrib import admin, messages
from django.utils.html import format_html
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from apps.orders.services import mark_order_paid

from .models import Invoice, Order, OrderItem


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    fields = [
        "product_name",
        "product_sku",
        "quantity",
        "unit_price",
        "line_total",
        "artwork_status",
        "artwork_file",
        "request_proof",
        "proof_status",
        "proof_image",
        "proof_sent_at",
        "proof_feedback",
    ]
    readonly_fields = ["product_name", "product_sku", "quantity", "unit_price", "line_total"]


class InvoiceInline(StackedInline):
    model = Invoice
    extra = 0
    fields = ["invoice_number", "issue_date", "taxable_base", "iva_amount", "total", "is_paid", "pdf_file"]
    readonly_fields = ["invoice_number", "issue_date", "taxable_base", "iva_amount", "total", "pdf_file"]


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = [
        "order_number",
        "full_name",
        "email",
        "nif_cif",
        "status_badge",
        "payment_method",
        "payment_status_badge",
        "total",
        "created_at",
    ]
    list_filter = ["status", "payment_status", "payment_method", "customer_type", "created_at"]
    search_fields = [
        "order_number",
        "first_name",
        "last_name",
        "email",
        "nif_cif",
        "company_name",
        "tracking_number",
    ]
    inlines = [OrderItemInline, InvoiceInline]
    readonly_fields = [
        "order_number",
        "access_token",
        "subtotal",
        "discount_amount",
        "shipping_cost",
        "taxable_base",
        "iva_amount",
        "total",
        "confirmation_email_sent",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            "Pedido",
            {
                "fields": (
                    "order_number",
                    "access_token",
                    "user",
                    "status",
                    "customer_notes",
                    "internal_notes",
                )
            },
        ),
        (
            "Cliente / Fiscal",
            {
                "fields": (
                    "customer_type",
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                    "company_name",
                    "nif_cif",
                )
            },
        ),
        (
            "Envío",
            {
                "fields": (
                    "shipping_address_line1",
                    "shipping_address_line2",
                    "shipping_postal_code",
                    "shipping_city",
                    "shipping_province",
                    "shipping_country",
                    "shipping_method_name",
                    "courier",
                    "tracking_number",
                    "tracking_url",
                )
            },
        ),
        (
            "Pago & Totales",
            {
                "fields": (
                    "payment_method",
                    "payment_status",
                    "subtotal",
                    "discount_amount",
                    "coupon_code",
                    "shipping_cost",
                    "taxable_base",
                    "iva_percentage",
                    "iva_amount",
                    "total",
                    "confirmation_email_sent",
                )
            },
        ),
        ("Auditoría", {"fields": ("created_at", "updated_at")}),
    )
    actions = [
        "mark_in_production",
        "mark_shipped",
        "confirm_bank_transfer_paid",
    ]

    def status_badge(self, obj):
        return obj.get_status_display()

    status_badge.short_description = "Estado Pedido"

    def payment_status_badge(self, obj):
        color = "green" if obj.is_paid else "amber"
        return format_html(
            '<span style="font-weight:bold; color: {}">{}</span>',
            color,
            obj.get_payment_status_display(),
        )

    payment_status_badge.short_description = "Pago"

    @admin.action(description="Marcar pedidos seleccionados En Producción")
    def mark_in_production(self, request, queryset):
        queryset.update(status=Order.Status.EN_PRODUCCION)

    @admin.action(description="Marcar pedidos seleccionados como Enviados")
    def mark_shipped(self, request, queryset):
        queryset.update(status=Order.Status.ENVIADO)

    @admin.action(description="Confirmar transferencia bancaria recibida (marcar Pagado)")
    def confirm_bank_transfer_paid(self, request, queryset):
        count = 0
        for order in queryset.filter(payment_method=Order.PaymentMethod.TRANSFER):
            if order.payment_status != Order.PaymentStatus.PAID:
                mark_order_paid(order, send_email=True)
                from apps.payments.models import Payment

                Payment.objects.filter(
                    order=order,
                    gateway=Payment.Gateway.TRANSFER,
                    status=Payment.Status.PENDING,
                ).update(status=Payment.Status.COMPLETED)
                count += 1
        self.message_user(
            request,
            f"{count} transferencia(s) confirmada(s) y marcadas como pagadas.",
            messages.SUCCESS,
        )


@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    list_display = [
        "invoice_number",
        "order_link",
        "issue_date",
        "taxable_base",
        "iva_amount",
        "total",
        "is_paid",
    ]
    list_filter = ["is_paid", "issue_date"]
    search_fields = ["invoice_number", "order__order_number", "order__nif_cif"]
    readonly_fields = [
        "invoice_number",
        "issue_date",
        "taxable_base",
        "iva_amount",
        "total",
        "company_data",
        "customer_data",
        "pdf_file",
        "created_at",
    ]

    def order_link(self, obj):
        return obj.order.order_number

    order_link.short_description = "Pedido"
