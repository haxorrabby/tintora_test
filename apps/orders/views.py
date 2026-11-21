"""
Checkout, confirmation and invoice download views.
"""
from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, View

from apps.cart.models import ShippingMethod
from apps.cart.services import CartService

from .models import Order
from .pdf import generate_invoice_pdf
from .services import (
    STATUS_SEQUENCE,
    CheckoutValidationError,
    process_checkout,
    status_rank,
    user_can_access_order,
)


class CheckoutView(TemplateView):
    """
    Editorial checkout:
    01 Datos fiscales · 02 Dirección y envío · 03 Pasarela de pago
    """

    template_name = "pages/checkout.html"

    def dispatch(self, request, *args, **kwargs):
        cart = CartService.get_or_create_cart(request)
        if cart.item_count == 0:
            messages.warning(
                request,
                _("Tu cesta está vacía. Añade productos antes de finalizar la compra."),
            )
            return redirect("cart:detail")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = CartService.get_or_create_cart(self.request)
        shipping_methods = ShippingMethod.objects.filter(is_active=True).select_related("zone")
        user = self.request.user if self.request.user.is_authenticated else None

        context.update(
            {
                "cart": cart,
                "shipping_methods": shipping_methods,
                "user": user,
                "page_title": _("Finalizar Pedido · Tintora Madrid"),
            }
        )
        return context


class CheckoutProcessView(View):
    """POST handler: validate → create order → payment → confirm or redirect."""

    def post(self, request: HttpRequest) -> HttpResponse:
        cart = CartService.get_or_create_cart(request)
        if cart.item_count == 0:
            return redirect("cart:detail")

        try:
            result = process_checkout(request, cart, request.POST)
        except CheckoutValidationError as exc:
            messages.error(request, exc.message)
            return redirect("orders:checkout")

        order = result.order
        payment = result.payment

        if payment.requires_redirect and payment.redirect_url:
            messages.info(
                request,
                _("Te redirigimos a la pasarela segura para completar el pago de %(num)s.")
                % {"num": order.order_number},
            )
            return redirect(payment.redirect_url)

        if payment.instructions:
            messages.info(request, payment.instructions)

        messages.success(
            request,
            _("¡Pedido %(num)s tramitado con éxito!") % {"num": order.order_number},
        )
        return redirect("orders:confirmation", order_number=order.order_number)


class OrderConfirmationView(TemplateView):
    """Order confirmation with production timeline."""

    template_name = "pages/order_confirmation.html"

    TIMELINE_STEPS = [
        (
            Order.Status.RECIBIDO,
            _("Pedido Recibido"),
            _("Tu encargo está registrado en nuestro sistema."),
            "check_circle",
        ),
        (
            Order.Status.REVISION_ARTE,
            _("Revisión de Arte (Fogra39)"),
            _("Verificamos perfiles de color ICC, sangrados y resolución mínima 300 dpi."),
            "palette",
        ),
        (
            Order.Status.PRUEBA_ENVIADA,
            _("Prueba Física Enviada"),
            _("Hemos enviado una prueba de impresión para tu aprobación."),
            "local_shipping",
        ),
        (
            Order.Status.EN_PRODUCCION,
            _("En Producción"),
            _("El pedido está en máquina. Sin posibilidad de cambios en arte."),
            "precision_manufacturing",
        ),
        (
            Order.Status.ENVIADO,
            _("Enviado"),
            _("Paquete entregado al transportista. Consulta el número de seguimiento."),
            "deployed_code",
        ),
        (
            Order.Status.ENTREGADO,
            _("Entregado"),
            _("¡Tu pedido ha llegado a su destino! Gracias por confiar en Tintora."),
            "done_all",
        ),
    ]

    def get(self, request, *args, **kwargs):
        order = get_object_or_404(Order, order_number=kwargs["order_number"])
        if not user_can_access_order(request, order):
            raise PermissionDenied(_("No tienes permiso para ver este pedido."))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = get_object_or_404(Order, order_number=self.kwargs["order_number"])
        current_rank = status_rank(order.status)

        steps_with_state = []
        for step_code, step_label, step_desc, step_icon in self.TIMELINE_STEPS:
            rank = status_rank(step_code)
            if order.status == Order.Status.CANCELADO:
                state = "cancelled"
            elif step_code == order.status:
                state = "current"
            elif rank < current_rank:
                state = "done"
            else:
                state = "upcoming"
            steps_with_state.append(
                {
                    "code": step_code,
                    "label": step_label,
                    "description": step_desc,
                    "icon": step_icon,
                    "state": state,
                }
            )

        context.update(
            {
                "order": order,
                "steps": steps_with_state,
                "status_sequence": STATUS_SEQUENCE,
                "page_title": _("Confirmación de Pedido %(num)s · Tintora Madrid")
                % {"num": order.order_number},
            }
        )
        return context


class InvoiceDownloadView(View):
    """Serve official PDF factura (session/owner/token gated)."""

    def get(self, request: HttpRequest, order_number: str) -> HttpResponse:
        order = get_object_or_404(Order.objects.select_related("invoice"), order_number=order_number)
        if not user_can_access_order(request, order):
            raise PermissionDenied(_("No tienes permiso para descargar esta factura."))
        if not hasattr(order, "invoice"):
            raise Http404(_("Factura no encontrada para este pedido."))

        invoice = order.invoice
        if invoice.pdf_file:
            try:
                pdf_bytes = invoice.pdf_file.read()
            except Exception:
                pdf_bytes = generate_invoice_pdf(invoice)
        else:
            pdf_bytes = generate_invoice_pdf(invoice)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        filename = f"Factura_Tintora_{invoice.invoice_number}.pdf"
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response
