from django.urls import path

from .views import (
    CheckoutProcessView,
    CheckoutView,
    InvoiceDownloadView,
    OrderConfirmationView,
)

app_name = "orders"

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("checkout/procesar/", CheckoutProcessView.as_view(), name="checkout_process"),
    path("checkout/confirmacion/<str:order_number>/", OrderConfirmationView.as_view(), name="confirmation"),
    path("pedidos/<str:order_number>/factura/", InvoiceDownloadView.as_view(), name="download_invoice"),
]
