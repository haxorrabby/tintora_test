"""
Celery tasks for order confirmation emails and invoice PDF persistence.
Falls back to synchronous execution when Celery/Redis is unavailable (dev).
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="orders.send_order_confirmation",
    max_retries=3,
    default_retry_delay=60,
)
def send_order_confirmation_task(self, order_id: int) -> bool:
    """Send confirmation email with PDF invoice attached."""
    from apps.orders.emails import send_order_confirmation_email
    from apps.orders.models import Order

    try:
        order = Order.objects.select_related("invoice").prefetch_related("items").get(pk=order_id)
    except Order.DoesNotExist:
        logger.error("Order %s not found for confirmation email.", order_id)
        return False

    try:
        ok = send_order_confirmation_email(order)
        if ok:
            # Persist PDF on invoice when generated
            persist_invoice_pdf(order_id)
        return ok
    except Exception as exc:
        logger.exception("Confirmation email failed for order %s: %s", order_id, exc)
        raise self.retry(exc=exc) from exc


@shared_task(name="orders.persist_invoice_pdf")
def persist_invoice_pdf(order_id: int) -> bool:
    """Generate and store invoice PDF on Invoice.pdf_file."""
    from apps.orders.models import Order
    from apps.orders.pdf import generate_invoice_pdf

    try:
        order = Order.objects.select_related("invoice").get(pk=order_id)
    except Order.DoesNotExist:
        return False

    if not hasattr(order, "invoice") or not order.invoice:
        return False

    invoice = order.invoice
    try:
        pdf_bytes = generate_invoice_pdf(invoice)
        filename = f"Factura_{invoice.invoice_number}.pdf"
        invoice.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
        return True
    except Exception:
        logger.exception("Failed to persist PDF for invoice %s", invoice.invoice_number)
        return False


def queue_order_confirmation(order_id: int) -> bool:
    """
    Prefer Celery; fall back to sync send so checkout never hard-depends on Redis.
    Returns True if email was dispatched (queued or sent).
    """
    try:
        send_order_confirmation_task.delay(order_id)
        return True
    except Exception:
        logger.warning("Celery unavailable – sending confirmation email synchronously.")
        try:
            return bool(send_order_confirmation_task(order_id))
        except Exception:
            logger.exception("Sync confirmation email failed for order %s", order_id)
            return False
