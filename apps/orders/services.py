"""
Checkout & order finalisation services.

Server-side price authority: all totals are taken from the Cart model,
never from client-submitted amounts.
"""
from __future__ import annotations

import re
import uuid
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.cart.models import Cart, Coupon, ShippingMethod
from apps.payments.gateways import PaymentResult, get_payment_gateway

from .models import Invoice, Order, OrderItem

# Spanish NIF/CIF/NIE: letter-optional + 7–8 digits + control char, optional hyphens
_NIF_RE = re.compile(
    r"^([XYZ]\d{7}[A-Z]|[ABCDEFGHJKLMNPQRSUVW]\d{7}[0-9A-J]|\d{8}[A-Z])$",
    re.IGNORECASE,
)

# Status order for timeline UI (not lexicographic)
STATUS_SEQUENCE: list[str] = [
    Order.Status.RECIBIDO,
    Order.Status.REVISION_ARTE,
    Order.Status.PRUEBA_ENVIADA,
    Order.Status.EN_PRODUCCION,
    Order.Status.ENVIADO,
    Order.Status.ENTREGADO,
]


def validate_spanish_tax_id(value: str) -> tuple[bool, str]:
    """Basic format check for NIF / CIF / NIE (not full AEAT checksum)."""
    cleaned = re.sub(r"[\s.\-]", "", (value or "").upper())
    if not cleaned:
        return False, str(_("El NIF/CIF/NIE es obligatorio para emitir factura."))
    if not _NIF_RE.match(cleaned):
        return False, str(
            _("El formato del NIF/CIF/NIE no es válido. Ejemplos: 12345678Z, B88776655, X1234567L.")
        )
    return True, cleaned


def status_rank(status: str) -> int:
    """Return timeline position; CANCELADO sorts as incomplete."""
    try:
        return STATUS_SEQUENCE.index(status)
    except ValueError:
        return -1


def company_fiscal_snapshot() -> dict[str, Any]:
    """Snapshot of Tintora fiscal data for invoice PDF persistence."""
    company = getattr(settings, "TINTORA_COMPANY", {}) or {}
    return {
        "NAME": company.get("NAME", "Tintora Impresión y Soluciones Creativas S.L."),
        "NIF_CIF": company.get("NIF_CIF", "B-88776655"),
        "ADDRESS": company.get(
            "ADDRESS",
            "C. Núñez de Balboa, 30, Loc 1, 28902 Getafe, Madrid, Spain",
        ),
        "PHONE": company.get("PHONE", ""),
        "EMAIL": company.get("EMAIL", "hola@tintora.es"),
    }


def customer_fiscal_snapshot(order: Order) -> dict[str, Any]:
    return {
        "name": order.full_name,
        "company_name": order.company_name,
        "nif_cif": order.nif_cif,
        "email": order.email,
        "phone": order.phone,
        "address": (
            f"{order.shipping_address_line1}, "
            f"{order.shipping_postal_code} {order.shipping_city} "
            f"({order.shipping_province})"
        ),
        "customer_type": order.customer_type,
    }


def grant_order_access(request: HttpRequest, order: Order) -> None:
    """Store access token in session so confirmation/PDF work without login."""
    tokens = request.session.get("order_access_tokens", {})
    tokens[order.order_number] = str(order.access_token)
    request.session["order_access_tokens"] = tokens
    request.session.modified = True


def user_can_access_order(request: HttpRequest, order: Order) -> bool:
    """Owner, staff, or session with matching access token."""
    user = request.user
    if user.is_authenticated:
        if user.is_staff or (order.user_id and order.user_id == user.id):
            return True
        if user.email and user.email.lower() == order.email.lower():
            return True
    tokens = request.session.get("order_access_tokens", {})
    stored = tokens.get(order.order_number)
    if stored and stored == str(order.access_token):
        return True
    # Allow query-string token from email links: ?token=<uuid>
    qs_token = request.GET.get("token", "")
    if qs_token and qs_token == str(order.access_token):
        grant_order_access(request, order)
        return True
    return False


@transaction.atomic
def allocate_order_number() -> str:
    """Race-safe sequential order number TIN-YYYY-NNNN."""
    from django.utils import timezone

    year = timezone.now().year
    prefix = f"TIN-{year}-"
    last = (
        Order.objects.select_for_update()
        .filter(order_number__startswith=prefix)
        .order_by("-id")
        .first()
    )
    if last and last.order_number:
        try:
            seq = int(last.order_number.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


@transaction.atomic
def allocate_invoice_number() -> str:
    """Race-safe sequential invoice number FAC-YYYY-NNNN."""
    from django.utils import timezone

    year = timezone.now().year
    prefix = f"FAC-{year}-"
    last = (
        Invoice.objects.select_for_update()
        .filter(invoice_number__startswith=prefix)
        .order_by("-id")
        .first()
    )
    if last:
        try:
            seq = int(last.invoice_number.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


def create_invoice_for_order(order: Order, *, is_paid: bool = False) -> Invoice:
    """Create official factura if missing; update paid flag if already exists."""
    if hasattr(order, "invoice") and order.invoice:
        invoice = order.invoice
        if is_paid and not invoice.is_paid:
            invoice.is_paid = True
            invoice.save(update_fields=["is_paid", "updated_at"])
        return invoice

    invoice = Invoice.objects.create(
        invoice_number=allocate_invoice_number(),
        order=order,
        taxable_base=order.taxable_base,
        iva_percentage=order.iva_percentage,
        iva_amount=order.iva_amount,
        total=order.total,
        company_data=company_fiscal_snapshot(),
        customer_data=customer_fiscal_snapshot(order),
        is_paid=is_paid,
    )
    return invoice


def increment_coupon_usage(coupon_code: str) -> None:
    if not coupon_code:
        return
    Coupon.objects.filter(code__iexact=coupon_code).update(uses_count=F("uses_count") + 1)


def clear_cart(cart: Cart) -> None:
    cart.items.all().delete()
    cart.coupon = None
    cart.shipping_method = None
    cart.save(update_fields=["coupon", "shipping_method", "updated_at"])


def copy_cart_items_to_order(order: Order, cart: Cart) -> None:
    for cart_item in cart.items.select_related("product").all():
        if cart_item.artwork_file or cart_item.artwork_status == cart_item.ArtworkStatus.UPLOADED:
            artwork_status = OrderItem.ArtworkStatus.UPLOADED
        else:
            artwork_status = OrderItem.ArtworkStatus.DESIGN_LATER

        OrderItem.objects.create(
            order=order,
            product=cart_item.product,
            product_name=cart_item.product.display_name,
            product_sku=cart_item.product.sku or "",
            variant_label=cart_item.product.variant_label,
            quantity=cart_item.quantity,
            unit_price=cart_item.unit_price,
            line_total=cart_item.line_total,
            configuration={
                **(cart_item.selected_options or {}),
                **({"variant": cart_item.product.variant_label} if cart_item.product.variant_label else {}),
            },
            artwork_file=cart_item.artwork_file,
            artwork_status=artwork_status,
            request_proof=cart_item.request_proof,
            proof_status=(
                OrderItem.ProofStatus.PENDING
                if cart_item.request_proof
                else OrderItem.ProofStatus.NOT_REQUESTED
            ),
        )


class CheckoutValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def validate_checkout_payload(data: dict[str, str], cart: Cart) -> dict[str, Any]:
    """Validate POST fields; raise CheckoutValidationError on failure."""
    inventory_quantities = {}
    inventory_products = {}
    for item in cart.items.select_related("product"):
        if item.product.tracks_inventory:
            inventory_products[item.product_id] = item.product
            inventory_quantities[item.product_id] = inventory_quantities.get(item.product_id, 0) + item.quantity
    for product_id, quantity in inventory_quantities.items():
        product = inventory_products[product_id]
        if product.stock <= 0 or quantity > product.stock:
            raise CheckoutValidationError(
                str(
                    _("La variante %(name)s no tiene stock suficiente; actualiza la cantidad antes de continuar.")
                    % {
                        "name": (
                            f"{product.display_name} ({product.variant_label})"
                            if product.variant_label
                            else product.display_name
                        )
                    }
                )
            )

    customer_type = data.get("customer_type", Order.CustomerType.INDIVIDUAL)
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    company_name = (data.get("company_name") or "").strip()
    nif_raw = (data.get("nif_cif") or "").strip()

    address_line1 = (data.get("shipping_address_line1") or "").strip()
    address_line2 = (data.get("shipping_address_line2") or "").strip()
    postal_code = (data.get("shipping_postal_code") or "").strip()
    city = (data.get("shipping_city") or "").strip()
    province = (data.get("shipping_province") or "Madrid").strip()
    customer_notes = (data.get("customer_notes") or "").strip()
    payment_method = data.get("payment_method", Order.PaymentMethod.TRANSFER)

    required = [first_name, last_name, email, phone, nif_raw, address_line1, postal_code, city]
    if not all(required):
        raise CheckoutValidationError(
            str(_("Por favor cumplimenta todos los campos obligatorios del formulario."))
        )

    if customer_type == Order.CustomerType.BUSINESS and not company_name:
        raise CheckoutValidationError(
            str(_("Para facturación de empresa es obligatorio indicar la razón social."))
        )

    ok, nif_or_msg = validate_spanish_tax_id(nif_raw)
    if not ok:
        raise CheckoutValidationError(nif_or_msg)
    nif_cif = nif_or_msg

    valid_methods = {c.value for c in Order.PaymentMethod}
    # Stripe temporarily disabled — keep code but reject at checkout
    if not getattr(settings, "PAYMENTS_STRIPE_ENABLED", False):
        valid_methods.discard(Order.PaymentMethod.STRIPE)

    if payment_method not in valid_methods:
        raise CheckoutValidationError(
            str(_("Método de pago no válido. Elige Bizum, Redsys o transferencia bancaria."))
        )

    # Shipping: prefer POST override, else cart selection
    shipping_method_id = data.get("shipping_method_id")
    shipping_method = None
    if shipping_method_id:
        shipping_method = ShippingMethod.objects.filter(
            pk=shipping_method_id, is_active=True
        ).select_related("zone").first()
    if shipping_method is None:
        shipping_method = cart.shipping_method
    if shipping_method is None:
        shipping_method = ShippingMethod.objects.filter(is_active=True).select_related("zone").first()

    if shipping_method and cart.shipping_method_id != shipping_method.id:
        cart.shipping_method = shipping_method
        cart.save(update_fields=["shipping_method", "updated_at"])

    shipping_name = shipping_method.name if shipping_method else "Envío Estándar"
    courier = shipping_method.get_courier_display() if shipping_method else "SEUR"

    return {
        "customer_type": customer_type,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "company_name": company_name,
        "nif_cif": nif_cif,
        "shipping_address_line1": address_line1,
        "shipping_address_line2": address_line2,
        "shipping_postal_code": postal_code,
        "shipping_city": city,
        "shipping_province": province,
        "customer_notes": customer_notes,
        "payment_method": payment_method,
        "shipping_method": shipping_method,
        "shipping_name": shipping_name,
        "courier": courier,
    }


class CheckoutResult:
    def __init__(
        self,
        order: Order,
        payment: PaymentResult,
        *,
        email_queued: bool = False,
    ):
        self.order = order
        self.payment = payment
        self.email_queued = email_queued


@transaction.atomic
def process_checkout(request: HttpRequest, cart: Cart, form_data: dict[str, str]) -> CheckoutResult:
    """
    Create order from cart, run payment gateway, then finalise according to result.

    - Immediate success (sim / Bizum / Redsys / transfer): invoice + email + clear cart
    - Stripe redirect: order PENDING, no invoice yet, cart cleared, email deferred to webhook
    - Failure: order marked FAILED, cart kept, no invoice
    """
    if cart.item_count == 0:
        raise CheckoutValidationError(str(_("Tu cesta está vacía.")))

    payload = validate_checkout_payload(form_data, cart)

    # Re-read money from cart (server authority)
    order = Order(
        user=request.user if request.user.is_authenticated else None,
        access_token=uuid.uuid4(),
        customer_type=payload["customer_type"],
        first_name=payload["first_name"],
        last_name=payload["last_name"],
        email=payload["email"],
        phone=payload["phone"],
        company_name=payload["company_name"],
        nif_cif=payload["nif_cif"],
        shipping_address_line1=payload["shipping_address_line1"],
        shipping_address_line2=payload["shipping_address_line2"],
        shipping_postal_code=payload["shipping_postal_code"],
        shipping_city=payload["shipping_city"],
        shipping_province=payload["shipping_province"],
        shipping_country="España",
        shipping_method_name=payload["shipping_name"],
        courier=payload["courier"],
        shipping_cost=cart.shipping_cost,
        payment_method=payload["payment_method"],
        subtotal=cart.subtotal,
        discount_amount=cart.discount_amount,
        coupon_code=cart.coupon.code if cart.coupon else "",
        taxable_base=cart.taxable_base,
        iva_percentage=Decimal(str(getattr(settings, "TINTORA_IVA_PERCENTAGE", 21))),
        iva_amount=cart.iva_amount,
        total=cart.total,
        customer_notes=payload["customer_notes"],
        confirmation_email_sent=False,
    )
    order.order_number = allocate_order_number()
    order.save()
    copy_cart_items_to_order(order, cart)

    gateway = get_payment_gateway(payload["payment_method"])
    result = gateway.process_payment(order, request)

    if not result.success:
        order.payment_status = Order.PaymentStatus.FAILED
        order.save(update_fields=["payment_status", "updated_at"])
        # Keep cart so the customer can retry
        raise CheckoutValidationError(
            result.error_message
            or str(_("No se ha podido procesar el pago. Inténtalo de nuevo o elige otro método."))
        )

    email_queued = False

    if result.requires_redirect:
        # Live Stripe: defer invoice + confirmation email until webhook
        clear_cart(cart)
        grant_order_access(request, order)
        return CheckoutResult(order, result, email_queued=False)

    # Immediate settlement (simulation, Bizum, Redsys) or pending transfer
    is_paid = order.payment_status == Order.PaymentStatus.PAID
    create_invoice_for_order(order, is_paid=is_paid)
    increment_coupon_usage(order.coupon_code)
    clear_cart(cart)
    grant_order_access(request, order)

    # Queue confirmation email (Celery if available, else sync)
    from .tasks import queue_order_confirmation

    email_queued = queue_order_confirmation(order.id)
    order.confirmation_email_sent = True
    order.save(update_fields=["confirmation_email_sent", "updated_at"])

    return CheckoutResult(order, result, email_queued=email_queued)


@transaction.atomic
def mark_order_paid(order: Order, *, transaction_id: str = "", send_email: bool = True) -> Order:
    """Idempotent payment finalisation used by webhooks and admin transfer confirm."""
    if order.payment_status != Order.PaymentStatus.PAID:
        order.payment_status = Order.PaymentStatus.PAID
        order.save(update_fields=["payment_status", "updated_at"])

    create_invoice_for_order(order, is_paid=True)

    if send_email and not order.confirmation_email_sent:
        from .tasks import queue_order_confirmation

        queue_order_confirmation(order.id)
        order.confirmation_email_sent = True
        order.save(update_fields=["confirmation_email_sent", "updated_at"])

    return order
