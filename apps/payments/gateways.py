"""
Payment gateway adapters.

Stripe: live Checkout Session when a real secret key is configured; otherwise simulation.
Bizum / Redsys: simulation stubs ready for merchant credentials (HMAC / redirect form).
Bank transfer: pending until admin marks as paid.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.http import HttpRequest
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.orders.models import Order

from .models import Payment


@dataclass
class PaymentResult:
    success: bool
    transaction_id: str = ""
    redirect_url: str | None = None
    error_message: str = ""
    requires_redirect: bool = False
    instructions: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)


class BasePaymentGateway(ABC):
    @property
    @abstractmethod
    def code(self) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def process_payment(self, order: Order, request: HttpRequest, **kwargs: Any) -> PaymentResult:
        """Processes or initiates payment for the given order."""
        pass


def _mark_invoice_paid_if_exists(order: Order) -> None:
    if hasattr(order, "invoice") and order.invoice:
        order.invoice.is_paid = True
        order.invoice.save(update_fields=["is_paid", "updated_at"])


class StripeGateway(BasePaymentGateway):
    code = "stripe"
    name = "Stripe"

    def process_payment(self, order: Order, request: HttpRequest, **kwargs: Any) -> PaymentResult:
        stripe_secret = getattr(settings, "STRIPE_SECRET_KEY", None) or ""

        if stripe_secret and not stripe_secret.startswith("sk_test_placeholder"):
            try:
                import stripe

                stripe.api_key = stripe_secret
                success_url = (
                    request.build_absolute_uri(
                        reverse("orders:confirmation", kwargs={"order_number": order.order_number})
                    )
                    + f"?token={order.access_token}&session_id={{CHECKOUT_SESSION_ID}}"
                )
                cancel_url = request.build_absolute_uri(reverse("orders:checkout"))

                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    line_items=[
                        {
                            "price_data": {
                                "currency": "eur",
                                "product_data": {
                                    "name": f"Pedido Tintora {order.order_number}",
                                    "description": (
                                        f"Impresión & Servicios Creativos Madrid "
                                        f"({order.items.count()} artículos)"
                                    ),
                                },
                                "unit_amount": int(order.total * Decimal("100")),
                            },
                            "quantity": 1,
                        }
                    ],
                    mode="payment",
                    customer_email=order.email,
                    client_reference_id=order.order_number,
                    success_url=success_url,
                    cancel_url=cancel_url,
                    metadata={"order_number": order.order_number},
                )

                Payment.objects.create(
                    order=order,
                    gateway=Payment.Gateway.STRIPE,
                    transaction_id=session.id,
                    amount=order.total,
                    status=Payment.Status.PENDING,
                    raw_response={"session_id": session.id, "url": session.url},
                )
                order.payment_status = Order.PaymentStatus.PENDING
                order.save(update_fields=["payment_status", "updated_at"])

                return PaymentResult(
                    success=True,
                    transaction_id=session.id,
                    redirect_url=session.url,
                    requires_redirect=True,
                    raw_data={"session_id": session.id},
                )
            except Exception as e:
                return PaymentResult(
                    success=False,
                    error_message=f"Error en pasarela Stripe: {e!s}",
                )

        # Development / Simulation Mode
        mock_tx_id = f"stripe_sim_{order.order_number}_{order.id}"
        Payment.objects.create(
            order=order,
            gateway=Payment.Gateway.STRIPE,
            transaction_id=mock_tx_id,
            amount=order.total,
            status=Payment.Status.COMPLETED,
            raw_response={"mode": "simulation", "status": "succeeded"},
        )
        order.payment_status = Order.PaymentStatus.PAID
        order.save(update_fields=["payment_status", "updated_at"])
        _mark_invoice_paid_if_exists(order)

        return PaymentResult(
            success=True,
            transaction_id=mock_tx_id,
            requires_redirect=False,
        )


class BizumGateway(BasePaymentGateway):
    """
    Bizum via Redsys in production. Without merchant credentials we simulate
    an instant successful mobile payment (dev / demo).
    """

    code = "bizum"
    name = "Bizum"

    def process_payment(self, order: Order, request: HttpRequest, **kwargs: Any) -> PaymentResult:
        merchant_code = getattr(settings, "REDSYS_MERCHANT_CODE", "") or ""
        if merchant_code and getattr(settings, "REDSYS_SECRET_KEY", ""):
            # Real Bizum rides on Redsys TPV — redirect form prepared for Phase 4+ credentials
            return RedsysGateway(bizum=True).process_payment(order, request, **kwargs)

        tx_id = f"bizum_sim_{order.order_number}"
        Payment.objects.create(
            order=order,
            gateway=Payment.Gateway.BIZUM,
            transaction_id=tx_id,
            amount=order.total,
            status=Payment.Status.COMPLETED,
            raw_response={"mode": "simulation", "provider": "bizum", "phone": order.phone},
        )
        order.payment_status = Order.PaymentStatus.PAID
        order.save(update_fields=["payment_status", "updated_at"])
        _mark_invoice_paid_if_exists(order)

        return PaymentResult(
            success=True,
            transaction_id=tx_id,
            instructions=_(
                "Pago Bizum confirmado con el número %(phone)s. Tu pedido pasa directamente a taller."
            )
            % {"phone": order.phone},
        )


class RedsysGateway(BasePaymentGateway):
    """
    Spanish bank TPV (Redsys). When REDSYS_* settings are present, builds a
    signed redirect payload; otherwise simulates success for local development.
    """

    code = "redsys"
    name = "Redsys (TPV Virtual)"

    def __init__(self, bizum: bool = False):
        self.bizum = bizum

    def process_payment(self, order: Order, request: HttpRequest, **kwargs: Any) -> PaymentResult:
        merchant_code = getattr(settings, "REDSYS_MERCHANT_CODE", "") or ""
        secret_key = getattr(settings, "REDSYS_SECRET_KEY", "") or ""
        terminal = getattr(settings, "REDSYS_TERMINAL", "001")
        env_url = getattr(
            settings,
            "REDSYS_URL",
            "https://sis-t.redsys.es:25443/sis/realizarPago",
        )

        if merchant_code and secret_key:
            order_id_redsys = str(order.id).zfill(4)[-12:]
            amount_cents = str(int(order.total * Decimal("100")))
            merchant_params = {
                "DS_MERCHANT_AMOUNT": amount_cents,
                "DS_MERCHANT_ORDER": order_id_redsys,
                "DS_MERCHANT_MERCHANTCODE": merchant_code,
                "DS_MERCHANT_CURRENCY": "978",
                "DS_MERCHANT_TRANSACTIONTYPE": "0",
                "DS_MERCHANT_TERMINAL": terminal,
                "DS_MERCHANT_MERCHANTURL": request.build_absolute_uri(
                    reverse("payments:redsys_notify")
                ),
                "DS_MERCHANT_URLOK": request.build_absolute_uri(
                    reverse("orders:confirmation", kwargs={"order_number": order.order_number})
                )
                + f"?token={order.access_token}",
                "DS_MERCHANT_URLKO": request.build_absolute_uri(reverse("orders:checkout")),
                "DS_MERCHANT_PRODUCTDESCRIPTION": f"Tintora {order.order_number}",
            }
            if self.bizum:
                merchant_params["DS_MERCHANT_PAYMETHODS"] = "z"

            params_b64 = base64.b64encode(
                json.dumps(merchant_params).encode("utf-8")
            ).decode("utf-8")
            signature = self._sign(params_b64, order_id_redsys, secret_key)

            Payment.objects.create(
                order=order,
                gateway=Payment.Gateway.BIZUM if self.bizum else Payment.Gateway.REDSYS,
                transaction_id=f"redsys_{order_id_redsys}",
                amount=order.total,
                status=Payment.Status.PENDING,
                raw_response={
                    "Ds_SignatureVersion": "HMAC_SHA256_V1",
                    "Ds_MerchantParameters": params_b64,
                    "Ds_Signature": signature,
                    "action": env_url,
                },
            )
            order.payment_status = Order.PaymentStatus.PENDING
            order.save(update_fields=["payment_status", "updated_at"])

            # Store signed form in session for template auto-post redirect page
            request.session["redsys_form"] = {
                "action": env_url,
                "Ds_SignatureVersion": "HMAC_SHA256_V1",
                "Ds_MerchantParameters": params_b64,
                "Ds_Signature": signature,
                "order_number": order.order_number,
            }
            request.session.modified = True

            return PaymentResult(
                success=True,
                transaction_id=f"redsys_{order_id_redsys}",
                redirect_url=reverse("payments:redsys_redirect"),
                requires_redirect=True,
                raw_data={"action": env_url},
            )

        # Simulation
        tx_id = f"redsys_sim_{order.order_number}"
        Payment.objects.create(
            order=order,
            gateway=Payment.Gateway.REDSYS,
            transaction_id=tx_id,
            amount=order.total,
            status=Payment.Status.COMPLETED,
            raw_response={"mode": "simulation", "authorisationCode": "123456"},
        )
        order.payment_status = Order.PaymentStatus.PAID
        order.save(update_fields=["payment_status", "updated_at"])
        _mark_invoice_paid_if_exists(order)

        return PaymentResult(
            success=True,
            transaction_id=tx_id,
            instructions=_("Pago verificado a través de la pasarela Redsys (simulación)."),
        )

    @staticmethod
    def _sign(params_b64: str, order_id: str, secret_key: str) -> str:
        """Redsys HMAC-SHA256 signature (simplified; production should use 3DES key diversify)."""
        try:
            key = base64.b64decode(secret_key)
        except Exception:
            key = secret_key.encode("utf-8")
        digest = hmac.new(key, (params_b64 + order_id).encode("utf-8"), hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")


class BankTransferGateway(BasePaymentGateway):
    code = "transfer"
    name = "Transferencia Bancaria"

    def process_payment(self, order: Order, request: HttpRequest, **kwargs: Any) -> PaymentResult:
        company = getattr(settings, "TINTORA_COMPANY", {})
        iban = getattr(settings, "TINTORA_BANK_IBAN", "ES76 0049 1500 0512 3456 7890")
        bic = getattr(settings, "TINTORA_BANK_BIC", "BSCHESMMXXX")

        tx_id = f"transf_{order.order_number}"
        Payment.objects.create(
            order=order,
            gateway=Payment.Gateway.TRANSFER,
            transaction_id=tx_id,
            amount=order.total,
            status=Payment.Status.PENDING,
            raw_response={"iban": iban, "bic": bic},
        )
        order.payment_status = Order.PaymentStatus.PENDING
        order.save(update_fields=["payment_status", "updated_at"])

        instructions = _(
            "Por favor realiza una transferencia de %(amount)s€ al IBAN: %(iban)s "
            "(%(holder)s) indicando en el concepto '%(order)s'. "
            "Tu pedido se pondrá en producción en cuanto recibamos el justificante."
        ) % {
            "amount": order.total,
            "iban": iban,
            "holder": company.get("NAME", "Tintora S.L."),
            "order": order.order_number,
        }

        return PaymentResult(
            success=True,
            transaction_id=tx_id,
            instructions=instructions,
        )


def get_payment_gateway(gateway_code: str) -> BasePaymentGateway:
    """Resolve gateway by code. Stripe is blocked while PAYMENTS_STRIPE_ENABLED is False."""
    from django.conf import settings as dj_settings

    if gateway_code == "stripe" and not getattr(dj_settings, "PAYMENTS_STRIPE_ENABLED", False):
        raise ValueError("Stripe está desactivado temporalmente. Elige Bizum, Redsys o transferencia.")

    gateways: dict[str, type[BasePaymentGateway]] = {
        "stripe": StripeGateway,
        "bizum": BizumGateway,
        "redsys": RedsysGateway,
        "transfer": BankTransferGateway,
    }
    # Default when unknown: bank transfer (not Stripe)
    gateway_class = gateways.get(gateway_code, BankTransferGateway)
    return gateway_class()
