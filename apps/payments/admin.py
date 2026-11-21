from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ["id", "order_link", "gateway", "amount", "currency", "status", "transaction_id", "created_at"]
    list_filter = ["gateway", "status", "created_at"]
    search_fields = ["transaction_id", "order__order_number", "order__email"]
    readonly_fields = ["order", "gateway", "transaction_id", "amount", "currency", "status", "raw_response", "error_message", "created_at"]

    def order_link(self, obj):
        return obj.order.order_number
    order_link.short_description = "Pedido"
