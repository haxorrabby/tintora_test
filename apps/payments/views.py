"""
Payment callbacks: Stripe webhook (dormant while Stripe is off),
Redsys notify + auto-post redirect form for TPV / Bizum.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.orders.models import Order
from apps.orders.services import mark_order_paid

from .models import Payment

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    """
    Stripe webhook handler. Inactive while PAYMENTS_STRIPE_ENABLED is False.
    Kept so enabling Stripe later only requires a settings flag + keys.
    """

    def post(self, request: HttpRequest) -> HttpResponse:
        if not getattr(settings, "PAYMENTS_STRIPE_ENABLED", False):
            logger.info("[Stripe Webhook] Stripe disabled – ignoring.")
            return HttpResponse(status=200)

        stripe_secret = getattr(settings, "STRIPE_SECRET_KEY", None)
        webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

        if not stripe_secret or stripe_secret.startswith("sk_test_placeholder"):
            logger.info("[Stripe Webhook] Simulation mode – ignoring webhook.")
            return HttpResponse(status=200)

        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        try:
            import stripe

            stripe.api_key = stripe_secret
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError:
            logger.warning("[Stripe Webhook] Invalid payload.")
            return HttpResponse(status=400)
        except Exception as exc:
            logger.warning("[Stripe Webhook] Verification failed: %s", exc)
            return HttpResponse(status=400)

        event_type = event["type"]
        logger.info("[Stripe Webhook] Event: %s", event_type)

        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            order_number = session.get("metadata", {}).get("order_number") or session.get(
                "client_reference_id", ""
            )
            self._handle_payment_completed(order_number, session["id"])
        elif event_type == "payment_intent.payment_failed":
            pi = event["data"]["object"]
            order_number = pi.get("metadata", {}).get("order_number", "")
            if order_number:
                self._handle_payment_failed(
                    order_number,
                    pi.get("last_payment_error", {}).get("message", ""),
                )

        return HttpResponse(status=200)

    @staticmethod
    def _handle_payment_completed(order_number: str, session_id: str) -> None:
        try:
            order = Order.objects.get(order_number=order_number)
        except Order.DoesNotExist:
            logger.error("[Stripe Webhook] Order not found: %s", order_number)
            return

        Payment.objects.filter(order=order, transaction_id=session_id).update(
            status=Payment.Status.COMPLETED
        )
        mark_order_paid(order, transaction_id=session_id, send_email=True)
        logger.info("[Stripe Webhook] Order %s marked PAID.", order_number)

    @staticmethod
    def _handle_payment_failed(order_number: str, error_message: str) -> None:
        try:
            order = Order.objects.get(order_number=order_number)
        except Order.DoesNotExist:
            return

        order.payment_status = Order.PaymentStatus.FAILED
        order.save(update_fields=["payment_status", "updated_at"])
        Payment.objects.filter(order=order, status=Payment.Status.PENDING).update(
            status=Payment.Status.FAILED,
            error_message=error_message or "Payment failed.",
        )


class RedsysRedirectView(View):
    """Auto-submits the signed Redsys form stored in session after checkout."""

    def get(self, request: HttpRequest) -> HttpResponse:
        form_data = request.session.get("redsys_form")
        if not form_data:
            return redirect("orders:checkout")
        return render(request, "pages/redsys_redirect.html", {"form": form_data})


@method_decorator(csrf_exempt, name="dispatch")
class RedsysNotifyView(View):
    """
    Asynchronous notification URL for Redsys (DS_MERCHANT_MERCHANTURL).
    Marks order paid when response code indicates success (0000–0099).
    """

    def post(self, request: HttpRequest) -> HttpResponse:
        params_b64 = request.POST.get("Ds_MerchantParameters", "")
        signature = request.POST.get("Ds_Signature", "")
        if not params_b64:
            return HttpResponseForbidden("Missing parameters")

        try:
            import base64
            import json

            decoded = json.loads(base64.b64decode(params_b64).decode("utf-8"))
        except Exception:
            logger.exception("[Redsys] Failed to decode merchant parameters.")
            return HttpResponse(status=400)

        response_code = str(decoded.get("Ds_Response", decoded.get("DS_RESPONSE", "")))
        order_id_raw = str(decoded.get("Ds_Order", decoded.get("DS_ORDER", "")))

        try:
            order_pk = int(order_id_raw.lstrip("0") or "0")
            order = Order.objects.get(pk=order_pk)
        except (Order.DoesNotExist, ValueError):
            logger.error("[Redsys] Order not found for Ds_Order=%s", order_id_raw)
            return HttpResponse(status=404)

        try:
            code_int = int(response_code)
            authorised = 0 <= code_int <= 99
        except ValueError:
            authorised = False

        if authorised:
            Payment.objects.filter(order=order, status=Payment.Status.PENDING).update(
                status=Payment.Status.COMPLETED,
                raw_response={"notify": decoded, "signature": signature},
            )
            mark_order_paid(order, send_email=True)
            logger.info("[Redsys] Order %s authorised (code %s).", order.order_number, response_code)
        else:
            order.payment_status = Order.PaymentStatus.FAILED
            order.save(update_fields=["payment_status", "updated_at"])
            Payment.objects.filter(order=order, status=Payment.Status.PENDING).update(
                status=Payment.Status.FAILED,
                error_message=f"Redsys response {response_code}",
                raw_response={"notify": decoded},
            )
            logger.warning(
                "[Redsys] Order %s failed (code %s).", order.order_number, response_code
            )

        return HttpResponse(status=200)
